import os
import cv2
import numpy as np
from typing import List, Union

class ImageToVideoConverter:
    def __init__(self, output_path: str = 'output_video.mp4', fps: int = 1):
        """
        Initialize the video converter
        
        :param output_path: Path where the output video will be saved
        :param fps: Frames per second (how long each image is shown)
        """
        self.output_path = output_path
        self.fps = fps
    
    def convert_images_to_video(self, image_folder: str) -> bool:
        """
        Convert images in a folder to a video
        
        :param image_folder: Path to folder containing images
        :return: True if video created successfully, False otherwise
        """
        # Get list of image files
        images = [f for f in os.listdir(image_folder) if f.endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))]
        images.sort()  # Sort images to ensure consistent order
        
        if not images:
            print("No images found in the specified folder.")
            return False
        
        # Read first image to get dimensions
        first_image_path = os.path.join(image_folder, images[0])
        frame = cv2.imread(first_image_path)
        height, width, layers = frame.shape
        
        # Define the codec and create VideoWriter object
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        out = cv2.VideoWriter(self.output_path, fourcc, self.fps, (width, height))
        
        # Write images to video
        for image in images:
            img_path = os.path.join(image_folder, image)
            frame = cv2.imread(img_path)
            
            # Resize image if needed to match first image's dimensions
            frame = cv2.resize(frame, (width, height))
            
            out.write(frame)
        
        # Release the video writer
        out.release()
        
        print(f"Video saved to {self.output_path}")
        return True
    
    @staticmethod
    def resize_images(image_folder: str, target_width: int = 1920, target_height: int = 1080) -> None:
        """
        Resize all images in a folder to a consistent size
        
        :param image_folder: Path to folder containing images
        :param target_width: Desired width of images
        :param target_height: Desired height of images
        """
        images = [f for f in os.listdir(image_folder) if f.endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))]
        
        for image in images:
            img_path = os.path.join(image_folder, image)
            img = cv2.imread(img_path)
            
            # Resize image
            resized_img = cv2.resize(img, (target_width, target_height), interpolation=cv2.INTER_AREA)
            
            # Overwrite original image
            cv2.imwrite(img_path, resized_img)
        
        print(f"Resized {len(images)} images to {target_width}x{target_height}")

def main():
    # Example usage
    converter = ImageToVideoConverter(output_path='my_video.mp4', fps=1)
    converter.convert_images_to_video('path/to/your/image/folder')
    
    # Optional: Resize images before conversion
    # converter.resize_images('path/to/your/image/folder')

if __name__ == '__main__':
    main()
