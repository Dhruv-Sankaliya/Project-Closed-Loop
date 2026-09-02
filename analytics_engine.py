#!/usr/bin/env python3
import sys
import os
import argparse
import json

def compute_analytics(mesh_path, output_json_path, output_txt_path):
    try:
        import trimesh
        mesh = trimesh.load(mesh_path)
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate(list(mesh.geometry.values()))
            
        dimensions = mesh.extents
        
        length_m = float(dimensions[0])
        width_m = float(dimensions[1])
        height_m = float(dimensions[2])
        footprint_area_sqm = float(length_m * width_m)
        volume_cu_m = float(mesh.volume) if mesh.is_watertight else float(length_m * width_m * height_m * 0.7)
        
        analytics = {
            "building_height_m": round(height_m, 2),
            "building_length_m": round(length_m, 2),
            "building_width_m": round(width_m, 2),
            "footprint_area_sqm": round(footprint_area_sqm, 2),
            "estimated_volume_cubic_m": round(volume_cu_m, 2),
            "vertex_count": len(mesh.vertices),
            "face_count": len(mesh.faces),
            "is_watertight": mesh.is_watertight
        }
        
        with open(output_json_path, 'w') as f:
            json.dump(analytics, f, indent=2)
            
        summary_text = (
            "==========================================\n"
            "   AI REAL-WORLD 3D METRIC ANALYTICS REPORT\n"
            "==========================================\n"
            f"Maximum Structure Height : {analytics['building_height_m']} meters\n"
            f"Bounding Length          : {analytics['building_length_m']} meters\n"
            f"Bounding Width           : {analytics['building_width_m']} meters\n"
            f"Footprint Roof Area      : {analytics['footprint_area_sqm']} sq meters\n"
            f"Estimated Structure Vol  : {analytics['estimated_volume_cubic_m']} cubic meters\n"
            f"Total 3D Mesh Vertices   : {analytics['vertex_count']:,}\n"
            f"Total 3D Mesh Polygons   : {analytics['face_count']:,}\n"
            f"Watertight Sealed        : {'YES' if analytics['is_watertight'] else 'NO'}\n"
            "==========================================\n"
        )
        
        with open(output_txt_path, 'w') as f:
            f.write(summary_text)
            
        print("\n" + summary_text)
        return True
    except Exception as e:
        print(f"[WARNING] Analytics calculation fallback: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="AI Real-World 3D Metric Analytics Engine")
    parser.add_argument("--input", required=True, help="Input OBJ/PLY mesh file")
    parser.add_argument("--json-out", required=True, help="Output JSON report file")
    parser.add_argument("--txt-out", required=True, help="Output TXT summary file")
    args = parser.parse_args()
    
    compute_analytics(args.input, args.json_out, args.txt_out)

if __name__ == '__main__':
    main()
