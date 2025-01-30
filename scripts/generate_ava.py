import torch
import os
from diffusers import DiffusionPipeline
from diffusers.utils import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables for the prompt
load_dotenv()

# Configure logging to suppress verbose outputs
logging.set_verbosity_error()

# Create a directory to store generated images if it doesn't exist
output_dir = "images_generated"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Generate the name for the generated image file based on a timestamp
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
image_name = f"{timestamp}_image.png"
image_path = os.path.join(output_dir, image_name)

# Load the base pipeline
base = DiffusionPipeline.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0",  # Base model for initial denoising
    variant="fp16",  # Explicitly set to 16-bit floating point
    torch_dtype=torch.float16,  # Use half-precision for performance
    use_safetensors=True,  # Use safetensors format for better security
    safety_checker=None,  # Disable safety checker
    requires_safety_checker=False,
)
base.to("mps")  # Set the device to Apple Silicon GPU (Metal Performance Shader)

# Load the refiner pipeline, sharing components with the base pipeline
refiner = DiffusionPipeline.from_pretrained(
    "stabilityai/stable-diffusion-xl-refiner-1.0",  # Refiner model
    variant="fp16",  # Explicitly set to 16-bit floating point
    text_encoder_2=base.text_encoder_2,  # Share the text encoder from the base pipeline
    vae=base.vae,  # Share the Variational Autoencoder from the base pipeline
    torch_dtype=torch.float16,  # Use half-precision for memory efficiency
    use_safetensors=True,
    safety_checker=None,  # Disable safety checker
    requires_safety_checker=False  # Allow running without the safety checker
)
refiner.to("mps")  # Set the device to the same Apple Silicon GPU

# Configure the number of inference steps and how they are split
n_steps = 100  # Total number of denoising steps
high_noise_frac = 0.8  # Percentage of steps allocated to the base pipeline (80%)

# Set up a random generator with a random seed
generator = torch.Generator("mps").manual_seed(987654321)

# The positive and negative prompts
prompt = os.getenv('PROMPT_AVA')  # Positive prompt (e.g., an artistic description)
negative_prompt = os.getenv('NEGATIVE_PROMPT')  # Negative prompt (undesired features, e.g., "blurry, low quality")

# Step 1: Generate a latent image using the base pipeline
image = base(
    prompt=prompt,  # Positive prompt
    negative_prompt=negative_prompt,  # Negative prompt
    generator=generator,  # Use the random generator
    num_inference_steps=n_steps,  # Total steps for inference
    denoising_end=high_noise_frac,  # Stop at 80% of the noise schedule
    output_type="latent",  # Produce a latent output
).images

# Step 2: Refine the latent image using the refiner pipeline
image = refiner(
    prompt=prompt,  # Use the same positive prompt
    negative_prompt=negative_prompt,  # Use the same negative prompt
    generator=generator,  # Use the same random generator
    num_inference_steps=n_steps,  # Total steps for inference
    denoising_start=high_noise_frac,  # Start refining at 80% of the noise schedule
    image=image,  # Use the latent image generated by the base pipeline
).images[0]

# Save the final refined image to the specified path
image.save(image_path)
print(f"Generated image saved at: {image_path}")
