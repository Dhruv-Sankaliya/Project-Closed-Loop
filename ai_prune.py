#!/usr/bin/env python3
import os
import sys
import argparse
import cv2
import numpy as np

def get_laplacian_var(img):
    """
    Computes the Laplacian variance of the image to estimate focus/blur.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()

def create_dynamic_mask(frame, mask_path):
    """
    Detects dynamic objects (vehicles and pedestrians) and generates a binary mask image.
    White (255) = Background to KEEP (buildings, roads, grass).
    Black (0) = Dynamic objects to ERASE (cars, buses, trucks, people).
    """
    h, w = frame.shape[:2]
    mask = np.ones((h, w), dtype=np.uint8) * 255
    
    # 1. HOG Pedestrian Detector (built into OpenCV)
    try:
        hog = cv2.HOGDescriptor()
        hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        (rects, _) = hog.detectMultiScale(frame, winStride=(8, 8), padding=(4, 4), scale=1.05)
        for (x, y, bw, bh) in rects:
            pad_x = int(bw * 0.15)
            pad_y = int(bh * 0.15)
            x1, y1 = max(0, x - pad_x), max(0, y - pad_y)
            x2, y2 = min(w, x + bw + pad_x), min(h, y + bh + pad_y)
            cv2.rectangle(mask, (x1, y1), (x2, y2), 0, -1)
    except Exception:
        pass
        
    # 2. Vehicle Silhouette & Shadow Contour Detector
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        dilated = cv2.dilate(edges, kernel, iterations=2)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        img_area = h * w
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if 0.001 * img_area < area < 0.06 * img_area:
                x, y, bw, bh = cv2.boundingRect(cnt)
                aspect_ratio = float(bw) / bh
                if 0.35 < aspect_ratio < 3.8:
                    pad_x = int(bw * 0.1)
                    pad_y = int(bh * 0.1)
                    x1, y1 = max(0, x - pad_x), max(0, y - pad_y)
                    x2, y2 = min(w, x + bw + pad_x), min(h, y + bh + pad_y)
                    cv2.rectangle(mask, (x1, y1), (x2, y2), 0, -1)
    except Exception:
        pass
        
    cv2.imwrite(mask_path, mask)

def main():
    parser = argparse.ArgumentParser(description="AI/Feature-Driven Smart Keyframe Extractor & Dynamic Object Masker")
    parser.add_argument("--video", required=True, help="Path to input video inside container")
    parser.add_argument("--output-dir", required=True, help="Directory to save extracted frames")
    parser.add_argument("--masks-dir", default=None, help="Directory to save corresponding binary masks")
    parser.add_argument("--sample-fps", type=float, default=5.0, help="Rate at which to sample frames for analysis")
    parser.add_argument("--blur-threshold", type=float, default=100.0, help="Laplacian variance threshold for blur detection")
    parser.add_argument("--min-overlap", type=float, default=0.30, help="Minimum visual overlap ratio to maintain continuity")
    parser.add_argument("--max-overlap", type=float, default=0.75, help="Maximum visual overlap ratio above which frames are pruned")
    parser.add_argument("--enable-masking", action="store_true", default=True, help="Enable AI dynamic object masking for car/pedestrian removal")
    
    args = parser.parse_args()
    
    video_path = args.video
    output_dir = args.output_dir
    masks_dir = args.masks_dir if args.masks_dir else os.path.join(os.path.dirname(output_dir), "masks")
    
    os.makedirs(output_dir, exist_ok=True)
    if args.enable_masking:
        os.makedirs(masks_dir, exist_ok=True)
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open video: {video_path}")
        sys.exit(1)
        
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps
    
    print(f"--- Smart Frame Extractor & AI Dynamic Masker started ---")
    print(f"Video duration: {duration:.2f}s | FPS: {fps:.2f}")
    print(f"Pruning settings: Blur threshold: {args.blur_threshold} | Max Overlap: {args.max_overlap}")
    print(f"AI Dynamic Object Masking: {'ENABLED' if args.enable_masking else 'DISABLED'}")
    
    # Initialize SIFT detector
    sift = cv2.SIFT_create(nfeatures=1000)
    bf = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
    
    frame_interval = int(round(fps / args.sample_fps))
    if frame_interval < 1:
        frame_interval = 1
        
    saved_count = 0
    blurry_count = 0
    redundant_count = 0
    
    ref_kps = None
    ref_des = None
    ref_timestamp = -999.0
    
    # We sample frames at the frame_interval
    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        if frame_idx % frame_interval == 0:
            timestamp_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
            timestamp_sec = timestamp_ms / 1000.0
            
            # 1. Blur Detection Check
            blur_val = get_laplacian_var(frame)
            if blur_val < args.blur_threshold:
                blurry_count += 1
                frame_idx += 1
                continue
                
            # Detect features for current frame
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            kps, des = sift.detectAndCompute(gray_frame, None)
            
            if des is None or len(kps) < 50:
                frame_idx += 1
                continue
                
            # 2. Match with reference keyframe to detect redundancy
            if ref_des is None:
                save_frame = True
            else:
                matches = bf.knnMatch(des, ref_des, k=2)
                good_matches = []
                for m, n in matches:
                    if m.distance < 0.75 * n.distance:
                        good_matches.append(m)
                        
                overlap_ratio = len(good_matches) / len(ref_kps)
                time_gap = timestamp_sec - ref_timestamp
                
                if overlap_ratio > args.max_overlap and time_gap < 4.0:
                    redundant_count += 1
                    save_frame = False
                else:
                    save_frame = True
                    
            if save_frame:
                img_name = f"frame_{int(timestamp_ms)}.jpg"
                img_path = os.path.join(output_dir, img_name)
                cv2.imwrite(img_path, frame)
                
                # Generate AI Dynamic Object Mask
                if args.enable_masking:
                    mask_path = os.path.join(masks_dir, img_name)
                    create_dynamic_mask(frame, mask_path)
                
                ref_kps = kps
                ref_des = des
                ref_timestamp = timestamp_sec
                saved_count += 1
                print(f"Saved keyframe + AI mask: {img_name} at {timestamp_sec:.2f}s (Blur value: {blur_val:.1f})")
                
        frame_idx += 1
        
    cap.release()
    print(f"\n--- Pruning & Masking Summary ---")
    print(f"Total analyzed frames: {frame_idx // frame_interval}")
    print(f"Saved Keyframes & AI Masks: {saved_count}")
    print(f"Discarded (Blurry): {blurry_count}")
    print(f"Discarded (Redundant): {redundant_count}")

if __name__ == '__main__':
    main()
