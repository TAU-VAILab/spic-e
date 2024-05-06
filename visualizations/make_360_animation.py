import argparse
import torch
import os
import cv2
import numpy as np
import matplotlib.pyplot as plt
from shap_e.models.download import load_model
from shap_e.util.notebooks import decode_latent_mesh
from blender_rendering import good_looking_render

parser = argparse.ArgumentParser()
parser.add_argument('-d', '--data_path', type=str, help='path to data', required=True)
parser.add_argument('-o', '--output_dir', type=str, help='path to output dir', required=True)
parser.add_argument('--resolution_x', type=int, default=800, help='output resolution on x axis', required=False)
parser.add_argument('--resolution_y', type=int, default=800, help='output resolution on y axis', required=False)
parser.add_argument('--num_frames', type=int, default=100, help='number of video frames', required=False)
parser.add_argument('--num_samples', type=int, default=100, help='number of samples for rendering', required=False)
parser.add_argument('--exposure', type=float, default=1.5, help='exposure in rendering', required=False)
parser.add_argument('--init_z_rotation', type=int, default=0, help='initial z axis rotation of shape', required=False)

def alpha_blend_with_mask(foreground, background, mask): # modified func from link
    # Convert uint8 to float
    foreground = foreground.astype(float)
    background = background.astype(float)

    # Normalize the mask mask to keep intensity between 0 and 1
    mask = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    mask = mask.astype(float) / 255

    # Multiply the foreground with the mask matte
    foreground = cv2.multiply(mask, foreground)

    # Multiply the background with ( 1 - mask )
    background = cv2.multiply(1.0 - mask, background)

    # Add the masked foreground and background.
    return cv2.add(foreground, background).astype(np.uint8)

def infer(args, device):
    xm = load_model('transmitter', device=device)

    # create output dir if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)   

    # load latent and add noise to it
    input_latent = torch.load(args.data_path)

    with torch.no_grad():
        # Rendering Latent
        t = decode_latent_mesh(xm, input_latent).tri_mesh()
        mesh_path = os.path.join(args.output_dir, "mesh.ply")
        with open(mesh_path, 'wb') as f:
            t.write_ply(f)
        
        for i in range(args.num_frames):
            rotation_addition = (360 / args.num_frames) * i
            z_rotation = args.init_z_rotation + rotation_addition
            good_looking_render(mesh_path, os.path.join(args.output_dir, f"frame_{i:05}.png"), 
                                                        z_rotation=z_rotation,
                                                        resolution_x=args.resolution_x,
                                                        resolution_y=args.resolution_y,
                                                        num_samples=args.num_samples, 
                                                        exposure=args.exposure)
        
        # Create video from all the frames in the output directory
        video_path = os.path.join(args.output_dir, "video.mp4")
        out = cv2.VideoWriter(video_path, cv2.VideoWriter_fourcc(*'mp4v'), 30, (args.resolution_x, args.resolution_y))
        for i in range(args.num_frames):
            img = cv2.imread(os.path.join(args.output_dir, f"frame_{i:05}.png"), cv2.IMREAD_UNCHANGED)
            mask = img[:,:,3]
            foreground = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            background = np.ones_like(foreground) * 255
            img = alpha_blend_with_mask(foreground, background, mask)
            out.write(img)
        out.release()


if __name__ == '__main__':
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    args = parser.parse_args()
    infer(args, device)