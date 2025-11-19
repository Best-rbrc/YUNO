"""
Pixel Art Generator - Converts photos to 64x64 pixel art
"""
import os
from pathlib import Path
from typing import Optional, Tuple
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance


class PixelArtGenerator:
    """Generates pixel art from photos optimized for RGB LED matrix display."""
    
    def __init__(self, target_size: Tuple[int, int] = (64, 64)):
        """
        Initialize the pixel art generator.
        
        Args:
            target_size: Target size (width, height) for pixel art
        """
        self.target_size = target_size
    
    def load_image(self, image_path: str) -> Optional[Image.Image]:
        """
        Load an image from file path.
        
        Args:
            image_path: Path to image file
        
        Returns:
            PIL Image or None on error
        """
        if not image_path or not os.path.exists(image_path):
            return None
        
        try:
            image = Image.open(image_path)
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            return image
        except Exception as e:
            print(f"   ⚠️  Error loading image {image_path}: {e}")
            return None
    
    def resize_with_preserve_aspect(self, image: Image.Image, target_size: Tuple[int, int]) -> Image.Image:
        """
        Resize image to fit target size while preserving aspect ratio.
        Uses letterboxing/pillarboxing to fit entire image without cropping.
        
        Args:
            image: PIL Image
            target_size: Target (width, height)
        
        Returns:
            Resized image with letterboxing if needed
        """
        width, height = target_size
        
        # Calculate aspect ratios
        img_aspect = image.width / image.height
        target_aspect = width / height
        
        # Resize to fit within target size (letterboxing/pillarboxing)
        if img_aspect > target_aspect:
            # Image is wider - fit to width
            new_width = width
            new_height = int(image.height * (width / image.width))
        else:
            # Image is taller - fit to height
            new_height = height
            new_width = int(image.width * (height / image.height))
        
        resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Create new image with target size and black background
        result = Image.new('RGB', (width, height), (0, 0, 0))
        
        # Paste resized image centered
        paste_x = (width - new_width) // 2
        paste_y = (height - new_height) // 2
        result.paste(resized, (paste_x, paste_y))
        
        return result
    
    def enhance_contrast(self, image: Image.Image, factor: float = 1.2) -> Image.Image:
        """
        Enhance contrast for better LED matrix display.
        
        Args:
            image: PIL Image
            factor: Contrast enhancement factor
        
        Returns:
            Enhanced image
        """
        enhancer = ImageEnhance.Contrast(image)
        return enhancer.enhance(factor)
    
    def reduce_colors(self, image: Image.Image, palette_size: int = 256) -> Image.Image:
        """
        Reduce colors using quantization for pixel art effect.
        
        Args:
            image: PIL Image
            palette_size: Number of colors in palette
        
        Returns:
            Quantized image
        """
        # Convert to quantized image
        quantized = image.quantize(colors=palette_size)
        # Convert back to RGB
        return quantized.convert('RGB')
    
    def generate_pixel_art(self, image_path: str, enhance: bool = True) -> Optional[np.ndarray]:
        """
        Generate pixel art from a photo file.
        
        Args:
            image_path: Path to photo file
            enhance: Whether to apply contrast enhancement
        
        Returns:
            NumPy array of shape (height, width, 3) with RGB values (0-255)
            or None on error
        """
        # Load image
        image = self.load_image(image_path)
        if image is None:
            return None
        
        # Resize to target size (preserving entire image, no cropping)
        image = self.resize_with_preserve_aspect(image, self.target_size)
        
        # Enhance contrast for better display
        if enhance:
            image = self.enhance_contrast(image, factor=1.8)
        
        # Reduce colors for pixel art effect
        image = self.reduce_colors(image, palette_size=64)
        
        # Convert to numpy array
        pixel_array = np.array(image)
        
        return pixel_array
    
    def generate_pixel_art_for_person(self, person_data: dict) -> Optional[np.ndarray]:
        """
        Generate pixel art for a person.
        
        Args:
            person_data: Dictionary with 'local_photo_path' key
        
        Returns:
            NumPy array of pixel art or None on error
        """
        photo_path = person_data.get('local_photo_path')
        if not photo_path:
            return None
        
        return self.generate_pixel_art(photo_path)
    
    def save_pixel_art(self, pixel_array: np.ndarray, output_path: str):
        """
        Save pixel art array as an image file.
        
        Args:
            pixel_array: NumPy array (height, width, 3)
            output_path: Output file path
        """
        image = Image.fromarray(pixel_array.astype('uint8'))
        image.save(output_path)
    
    def pixel_art_to_matrix_format(self, pixel_array: np.ndarray) -> np.ndarray:
        """
        Convert pixel art array to format suitable for RGB matrix display.
        
        Args:
            pixel_array: NumPy array (height, width, 3) with RGB values (0-255)
        
        Returns:
            NumPy array ready for matrix display (height, width, 3)
        """
        # Ensure values are in correct range
        pixel_array = np.clip(pixel_array, 0, 255).astype(np.uint8)
        return pixel_array


if __name__ == "__main__":
    # Test the pixel art generator
    import sys
    
    print("Testing Pixel Art Generator...")
    generator = PixelArtGenerator(target_size=(64, 64))
    
    if len(sys.argv) > 1:
        test_image_path = sys.argv[1]
        print(f"Processing: {test_image_path}")
        
        pixel_art = generator.generate_pixel_art(test_image_path)
        if pixel_art is not None:
            print(f"✅ Generated pixel art: {pixel_art.shape}")
            
            # Save test output
            output_path = Path(__file__).parent / "test_output" / "pixel_art.jpg"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            generator.save_pixel_art(pixel_art, str(output_path))
            print(f"✅ Saved to: {output_path}")
        else:
            print("❌ Failed to generate pixel art")
    else:
        print("Usage: python pixel_art_generator.py <image_path>")

