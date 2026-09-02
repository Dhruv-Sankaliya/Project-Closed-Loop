#!/usr/bin/env python3
import os
import sys
import re
import argparse
import subprocess
import shutil

def parse_srt(srt_path):
    """
    Parses the SRT subtitle file and extracts GPS coordinates with millisecond precision.
    """
    if not os.path.exists(srt_path):
        return []
        
    with open(srt_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    blocks = content.strip().split('\n\n')
    data = []
    for block in blocks:
        lines = block.split('\n')
        if len(lines) < 4:
            continue
        try:
            block_num = int(lines[0].strip())
        except ValueError:
            continue
        text = lines[3]
        
        lat_match = re.search(r'latitude:\s*([-+]?\d*\.\d+|\d+)', text)
        lon_match = re.search(r'longitude:\s*([-+]?\d*\.\d+|\d+)', text)
        rel_alt_match = re.search(r'rel_alt:\s*([-+]?\d*\.\d+|\d+)', text)
        abs_alt_match = re.search(r'abs_alt:\s*([-+]?\d*\.\d+|\d+)', text)
        
        if lat_match and lon_match:
            lat = float(lat_match.group(1))
            lon = float(lon_match.group(1))
            rel_alt = float(rel_alt_match.group(1)) if rel_alt_match else 0.0
            abs_alt = float(abs_alt_match.group(1)) if abs_alt_match else 0.0
            data.append({
                'sec': block_num - 1,
                'lat': lat,
                'lon': lon,
                'rel_alt': rel_alt,
                'abs_alt': abs_alt
            })
    return data

def interpolate_gps(sec, telemetry_data, loop_period):
    """
    Interpolates GPS coordinates linearly for sub-second precision.
    Supports trajectory wrapping for circular flights.
    """
    # Apply loop wrapping
    wrapped_sec = sec % loop_period
    
    # Map coordinates by second
    gps_map = {d['sec']: (d['lon'], d['lat'], d['abs_alt']) for d in telemetry_data}
    
    sec_lower = int(wrapped_sec)
    sec_upper = (sec_lower + 1) % loop_period
    fraction = wrapped_sec - sec_lower
    
    if sec_lower in gps_map and sec_upper in gps_map:
        lon1, lat1, alt1 = gps_map[sec_lower]
        lon2, lat2, alt2 = gps_map[sec_upper]
        
        # Handle coordinate interpolation
        lon = lon1 + fraction * (lon2 - lon1)
        lat = lat1 + fraction * (lat2 - lat1)
        alt = alt1 + fraction * (alt2 - alt1)
        return lon, lat, alt
    elif sec_lower in gps_map:
        return gps_map[sec_lower]
    else:
        # Fallback to first available point
        first_sec = sorted(gps_map.keys())[0]
        return gps_map[first_sec]

def run_command(cmd, desc):
    print(f"\n[INFO] {desc}...")
    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print(f"[ERROR] Failed to: {desc}")
        print(result.stderr)
        return False, result.stdout, result.stderr
    return True, result.stdout, result.stderr

def main():
    parser = argparse.ArgumentParser(description="Single-Pass AI Drone Video 3D Reconstruction Pipeline")
    parser.add_argument("video", help="Path to the input drone MP4/MOV video file")
    parser.add_argument("--output-dir", help="Project output directory (defaults to current dir / output_project)")
    parser.add_argument("--sample-fps", type=float, default=5.0, help="Video sampling rate inside container (default: 5.0 fps)")
    parser.add_argument("--quality", choices=["high", "medium", "low", "lowest"], default="medium", help="Reconstruction quality (default: medium)")
    parser.add_argument("--blur-threshold", type=float, default=100.0, help="Laplacian variance threshold for blur detection (default: 100.0)")
    parser.add_argument("--max-overlap", type=float, default=0.75, help="SIFT keypoint overlap prune threshold (default: 0.75)")
    parser.add_argument("--cpu", action="store_true", help="Force CPU-only mode (uses opendronemap/odm instead of odm:gpu)")
    parser.add_argument("--max-concurrency", type=int, default=4, help="Maximum CPU threads to use (default: 4 to prevent RAM freeze)")
    
    args = parser.parse_args()
    docker_image = "opendronemap/odm" if args.cpu else "opendronemap/odm:gpu"
    
    video_path = os.path.abspath(args.video)
    if not os.path.exists(video_path):
        print(f"[ERROR] Video file not found: {video_path}")
        sys.exit(1)
        
    video_dir = os.path.dirname(video_path)
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    
    # Establish project directory
    if args.output_dir:
        project_dir = os.path.abspath(args.output_dir)
    else:
        project_dir = os.path.join(os.getcwd(), f"{video_name}_reconstruction")
        
    images_dir = os.path.join(project_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    
    print(f"==========================================")
    print(f"AI Drone 3D Reconstruction Pipeline (Active)")
    print(f"==========================================")
    print(f"Input Video: {video_path}")
    print(f"Project Output: {project_dir}")
    print(f"Quality: {args.quality}")
    print(f"Pruning overlap limit: {args.max_overlap}")
    print(f"Blur threshold: {args.blur_threshold}")
    
    # Copy video file temporarily inside project directory for Docker mapping
    temp_video_name = f"{video_name}.mp4"
    temp_video_path = os.path.join(images_dir, temp_video_name)
    shutil.copy2(video_path, temp_video_path)
    
    # Step 1: Attempt to extract subtitle track from video container using ffmpeg inside Docker
    srt_filename = f"{video_name}.SRT"
    temp_srt_path = os.path.join(images_dir, srt_filename)
    
    extract_srt_cmd = [
        "docker", "run", "--rm",
        "--entrypoint", "ffmpeg",
        "-v", f"{images_dir}:/datasets/images",
        docker_image,
        "-y", "-i", f"/datasets/images/{temp_video_name}",
        "-map", "0:s:0", f"/datasets/images/{srt_filename}"
    ]
    
    success, _, _ = run_command(extract_srt_cmd, "Extract embedded subtitles telemetry")
    
    # If container extraction fails, check for a sidecar SRT file next to the input video
    telemetry_data = []
    if not success or not os.path.exists(temp_srt_path) or os.path.getsize(temp_srt_path) == 0:
        print("[WARNING] Could not extract embedded subtitles. Checking for sidecar .SRT file next to video...")
        
        sidecar_candidates = [
            os.path.join(video_dir, f"{video_name}.SRT"),
            os.path.join(video_dir, f"{video_name}.srt"),
            os.path.join(video_dir, f"{video_name.lower()}.srt"),
            os.path.join(video_dir, f"{video_name.upper()}.SRT"),
        ]
        
        found_sidecar = None
        for candidate in sidecar_candidates:
            if os.path.exists(candidate):
                found_sidecar = candidate
                break
                
        if found_sidecar:
            print(f"[INFO] Found sidecar telemetry file: {found_sidecar}")
            shutil.copy2(found_sidecar, temp_srt_path)
        else:
            print(f"[ERROR] No telemetry subtitles found (neither embedded nor as a sidecar .SRT file).")
            print("Reconstruction cannot proceed without telemetry constraints.")
            shutil.rmtree(project_dir)
            sys.exit(1)
            
    # Parse GPS data
    telemetry_data = parse_srt(temp_srt_path)
    if not telemetry_data:
        print("[ERROR] Subtitle file parsed but no GPS coordinates found!")
        sys.exit(1)
        
    print(f"[INFO] Successfully loaded telemetry data. Extracted {len(telemetry_data)} GPS points.")
    
    # Step 2: Run AI Smart Frame Extractor inside the container
    # Copy the helper script into the project directory
    helper_script_source = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_prune.py")
    if os.path.exists(helper_script_source) and helper_script_source != os.path.join(project_dir, "ai_prune.py"):
        shutil.copy2(helper_script_source, os.path.join(project_dir, "ai_prune.py"))
        
    run_ai_pruner_cmd = [
        "docker", "run", "--rm",
        "--entrypoint", "python3",
        "-v", f"{project_dir}:/datasets/project",
        docker_image,
        "/datasets/project/ai_prune.py",
        "--video", f"/datasets/project/images/{temp_video_name}",
        "--output-dir", "/datasets/project/images",
        "--sample-fps", str(args.sample_fps),
        "--blur-threshold", str(args.blur_threshold),
        "--max-overlap", str(args.max_overlap)
    ]
    
    success, _, _ = run_command(run_ai_pruner_cmd, "Execute AI & Feature-driven smart keyframe selection")
    if not success:
        sys.exit(1)
        
    # Clean up temp video and helper python scripts from the images folder
    if os.path.exists(temp_video_path):
        os.remove(temp_video_path)
    if os.path.exists(os.path.join(project_dir, "ai_prune.py")):
        os.remove(os.path.join(project_dir, "ai_prune.py"))
        
    # Step 3: Match extracted keyframes to interpolated GPS data and write geo.txt
    all_files = os.listdir(images_dir)
    extracted_images = sorted([f for f in all_files if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
    
    loop_period = len(telemetry_data)
    
    geo_lines = ["EPSG:4326"]
    matched_count = 0
    
    for img in extracted_images:
        # Match format: frame_{timestamp_ms}.jpg
        match = re.match(r'frame_(\d+)\.(jpg|jpeg|png)', img, re.IGNORECASE)
        if not match:
            continue
            
        timestamp_ms = float(match.group(1))
        timestamp_sec = timestamp_ms / 1000.0
        
        # Calculate sub-second coordinate using linear interpolation
        lon, lat, alt = interpolate_gps(timestamp_sec, telemetry_data, loop_period)
        geo_lines.append(f"{img} {lon} {lat} {alt}")
        matched_count += 1
        
    geo_txt_path = os.path.join(project_dir, "geo.txt")
    with open(geo_txt_path, 'w') as f:
        f.write('\n'.join(geo_lines) + '\n')
        
    print(f"[INFO] Wrote geo.txt with {matched_count} AI-selected frames georeferenced.")
    
    # Step 4: Run OpenDroneMap (ODM) Docker container
    odm_cmd = [
        "docker", "run", "--rm",
        "-v", f"{project_dir}:/datasets/project",
    ]
    if not args.cpu:
        odm_cmd.extend(["--gpus", "all"])
    odm_cmd.extend([
        docker_image,
        "--project-path", "/datasets", "project",
        "--feature-quality", args.quality,
        "--pc-quality", args.quality,
        "--max-concurrency", str(args.max_concurrency)
    ])
    
    success, _, _ = run_command(odm_cmd, "Execute OpenDroneMap 3D reconstruction")
    if success:
        textured_obj = os.path.join(project_dir, 'odm_texturing', 'odm_textured_model_geo.obj')
        watertight_obj = os.path.join(project_dir, 'odm_texturing', 'odm_textured_model_watertight.obj')
        analytics_json = os.path.join(project_dir, 'analytics_report.json')
        analytics_txt = os.path.join(project_dir, 'analytics_summary.txt')
        
        # Step 5: Run AI 3D Mesh Hole Completer
        if os.path.exists(textured_obj):
            print("\n[INFO] Running AI 3D Building Completion & Watertight Sealer...")
            import mesh_completer
            mesh_completer.fill_holes(textured_obj, watertight_obj)
            
            # Step 6: Run Real-World 3D Metric Analytics Engine
            print("\n[INFO] Running AI Real-World 3D Metric Analytics Engine...")
            import analytics_engine
            target_mesh = watertight_obj if os.path.exists(watertight_obj) else textured_obj
            analytics_engine.compute_analytics(target_mesh, analytics_json, analytics_txt)
            
        print("\n==========================================")
        print("[SUCCESS] Master Single-Pass Pipeline Complete!")
        print(f"Textured Model  : {textured_obj}")
        if os.path.exists(watertight_obj):
            print(f"Watertight Model: {watertight_obj}")
        print(f"Point Cloud     : {os.path.join(project_dir, 'odm_filterpoints', 'point_cloud.ply')}")
        print(f"Orthophoto Map  : {os.path.join(project_dir, 'odm_orthophoto', 'odm_orthophoto.tif')}")
        print(f"Metric Report   : {analytics_txt}")
        print("==========================================")
    else:
        print("[ERROR] Reconstruction failed.")
        sys.exit(1)

if __name__ == '__main__':
    main()
