# Version 1.0.1 - Fixed indentation
import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import requests
from PIL import Image
import os
from image_to_video import ImageToVideoConverter
import tempfile
import uuid
import io
import json
import stripe
import base64
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

# Set page config
st.set_page_config(page_title="AI Video Generator Pro", layout="wide")

# Constants
SD_URL = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"

# Initialize default config with hashed password
hashed_passwords = stauth.Hasher(['abc123']).generate()

config = {
    'credentials': {
        'usernames': {
            'demo': {
                'email': 'demo@example.com',
                'name': 'Demo User',
                'password': hashed_passwords[0]
            }
        }
    },
    'cookie': {
        'expiry_days': 30,
        'key': 'some_signature_key',
        'name': 'some_cookie_name'
    },
    'preauthorized': {
        'emails': ['demo@example.com']
    }
}

# Initialize authenticator
authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
    config['preauthorized']
)

# Create necessary directories
for folder in ['uploads', 'generated', 'output']:
    os.makedirs(folder, exist_ok=True)

# Initialize session state
if 'user_usage' not in st.session_state:
    st.session_state.user_usage = {}
