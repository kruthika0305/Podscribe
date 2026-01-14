import os
from uuid import uuid4
import streamlit as st
import requests
from bs4 import BeautifulSoup
import certifi
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import re
from urllib.parse import urlparse
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# App Branding Configuration
APP_NAME = "PodScribe AI"
APP_TAGLINE = "Transform Written Words into Engaging Audio Narratives"
APP_VERSION = "1.0.0"
APP_AUTHOR = "AI Innovation Lab"

# Azure OpenAI Configuration from environment variables
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY", "")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_DEPLOYMENT_NAME = os.getenv("AZURE_DEPLOYMENT_NAME", "")
AZURE_API_VERSION = os.getenv("AZURE_API_VERSION", "")

# ElevenLabs Configuration from environment variables
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVEN_VOICE_ID = os.getenv("ELEVEN_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")

# App Configuration
SAVE_DIR = os.getenv("SAVE_DIR", "audio_generations")
os.makedirs(SAVE_DIR, exist_ok=True)

# Page configuration must be first Streamlit command
st.set_page_config(
    page_title=f"{APP_NAME} - AI-Powered Blog to Podcast Converter", 
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for enhanced branding
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    .main-header {
        text-align: center;
        padding: 2.5rem 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 20px;
        margin-bottom: 2rem;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
    }
    
    .main-title {
        color: white;
        font-size: 3.5rem;
        font-weight: 700;
        margin: 0;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    
    .tagline {
        color: #f0f0f0;
        font-size: 1.3rem;
        margin-top: 0.5rem;
        font-weight: 300;
    }
    
    .feature-box {
        background: linear-gradient(145deg, #ffffff, #f0f0f0);
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        box-shadow: 5px 5px 15px #d0d0d0, -5px -5px 15px #ffffff;
        transition: transform 0.3s ease;
    }
    
    .feature-box:hover {
        transform: translateY(-5px);
    }
    
    .stats-card {
        background: linear-gradient(145deg, #f9f9f9, #e0e0e0);
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin: 0.5rem;
    }
    
    .process-step {
        background: white;
        padding: 1rem;
        border-left: 4px solid #667eea;
        margin: 0.5rem 0;
        border-radius: 5px;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-weight: 600;
        padding: 0.75rem 2rem;
        border: none;
        border-radius: 10px;
        font-size: 1.1rem;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: scale(1.05);
        box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
    }
    
    .footer {
        text-align: center;
        color: #888;
        padding: 2rem;
        background: #f8f9fa;
        border-radius: 10px;
        margin-top: 3rem;
    }
    </style>
    """, unsafe_allow_html=True)

# Initialize OpenAI client
try:
    from openai import AzureOpenAI
    client = AzureOpenAI(
        api_key=AZURE_OPENAI_KEY,
        api_version=AZURE_API_VERSION,
        azure_endpoint=AZURE_OPENAI_ENDPOINT
    )
    USE_NEW_API = True
except ImportError:
    try:
        import openai
        openai.api_type = "azure"
        openai.api_key = AZURE_OPENAI_KEY
        openai.api_base = AZURE_OPENAI_ENDPOINT
        openai.api_version = AZURE_API_VERSION
        client = None
        USE_NEW_API = False
    except ImportError:
        raise RuntimeError("The 'openai' package is required. Install with: python -m pip install openai")

# Setup requests session
_session = requests.Session()
_retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
_session.mount("https://", HTTPAdapter(max_retries=_retries))
_session.mount("http://", HTTPAdapter(max_retries=_retries))


def scrape_blog(page_url: str, max_chars: int = 25000) -> tuple:
    """Scrape article content from URL."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        resp = _session.get(page_url, headers=headers, timeout=15, verify=certifi.where())
        resp.raise_for_status()
    except requests.exceptions.SSLError:
        try:
            resp = _session.get(page_url, headers=headers, timeout=15, verify=False)
            resp.raise_for_status()
        except Exception as e:
            st.error(f"🔒 SSL Error: {e}")
            return "", ""
    except Exception as e:
        st.error(f"❌ Scraping error: {e}")
        return "", ""

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        
        title = ""
        if soup.title:
            title = soup.title.string.strip() if soup.title.string else ""
        elif soup.find('h1'):
            title = soup.find('h1').get_text().strip()
        
        node = soup.find("article") or soup.find("main")
        paras = node.find_all("p") if node else soup.find_all("p")
        text_parts = [p.get_text().strip() for p in paras if p.get_text().strip()]
        text = "\n\n".join(text_parts)
        return text[:max_chars], title
    except Exception as e:
        st.error(f"⚠️ Parsing error: {e}")
        return "", ""


def create_safe_filename(url: str, title: str) -> str:
    """Create a safe filename from URL or title."""
    if title:
        safe_name = re.sub(r'[^\w\s-]', '', title)
        safe_name = re.sub(r'[-\s]+', '_', safe_name)
        safe_name = safe_name[:50]
    else:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.replace('www.', '')
        safe_name = re.sub(r'[^\w\s-]', '', domain)
    
    if not safe_name:
        safe_name = "podcast"
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    return f"{safe_name}_{timestamp}_podcast"


def summarize_with_azure_openai(article_text: str) -> str:
    """Summarize article using Azure OpenAI."""
    system_prompt = (
        "You are a professional podcast script writer. Create a concise, engaging, conversational summary "
        "of the article that sounds natural when spoken aloud. Use a warm, friendly tone. "
        "Include transitions and make it flow smoothly. Limit to 2000 characters."
        "Do NOT include intro music fades in and Host in the script ."
        "Make it interactive by starting with Hello Everyone! Today we're diving into an exciting topic."

    )
    user_prompt = f"Transform this article into an engaging podcast script:\n\n{article_text}"
    
    try:
        if USE_NEW_API:
            response = client.chat.completions.create(
                model=AZURE_DEPLOYMENT_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=800
            )
            content = response.choices[0].message.content.strip()
        else:
            import openai
            response = openai.ChatCompletion.create(
                engine=AZURE_DEPLOYMENT_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=800
            )
            content = response["choices"][0]["message"]["content"].strip()
        
        return content[:2000]
    except Exception as e:
        st.error(f"🤖 AI Error: {e}")
        return ""


# ...existing code until the TTS functions...

def elevenlabs_tts(text: str, filename: str) -> bool:
    """Generate audio using ElevenLabs TTS with fallback options."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.5,
            "use_speaker_boost": True
        }
    }
    
    try:
        resp = _session.post(url, json=payload, headers=headers, stream=True, timeout=60, verify=certifi.where())
        if resp.status_code == 401:
            # Silently fallback without warning
            return edge_tts_fallback(text, filename)
        resp.raise_for_status()
        
        with open(filename, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return True
    except requests.exceptions.SSLError:
        try:
            resp = _session.post(url, json=payload, headers=headers, stream=True, timeout=60, verify=False)
            if resp.status_code == 401:
                # Silently fallback without warning
                return edge_tts_fallback(text, filename)
            resp.raise_for_status()
            with open(filename, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
        except Exception as e:
            # Silently fallback
            return edge_tts_fallback(text, filename)
    except Exception as e:
        # Silently fallback
        return edge_tts_fallback(text, filename)


def edge_tts_fallback(text: str, filename: str) -> bool:
    """Free TTS using edge-tts (Microsoft Edge's TTS) as fallback."""
    try:
        import edge_tts
        import asyncio
        
        async def generate():
            voice = "en-US-AriaNeural"  # Professional female voice
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(filename)
        
        asyncio.run(generate())
        # Remove the info message
        return True
        
    except ImportError:
        # Silently try offline TTS
        return pyttsx3_fallback(text, filename)
    except Exception as e:
        # Silently try offline TTS
        return pyttsx3_fallback(text, filename)


def pyttsx3_fallback(text: str, filename: str) -> bool:
    """Offline TTS using pyttsx3 as last resort."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)  # Speed of speech
        engine.setProperty('volume', 0.9)  # Volume level (0.0 to 1.0)
        
        # Get available voices and set a female voice if available
        voices = engine.getProperty('voices')
        for voice in voices:
            if "female" in voice.name.lower():
                engine.setProperty('voice', voice.id)
                break
        
        engine.save_to_file(text, filename)
        engine.runAndWait()
        # Remove the info message
        return True
    except ImportError:
        # Final fallback - return False without error messages
        return False
    except Exception as e:
        # Silently fail
        return False

# ...rest of the code remains the same...
# Main UI Header
st.markdown(f"""
    <div class="main-header">
        <h1 class="main-title">🎙️ {APP_NAME}</h1>
        <p class="tagline">{APP_TAGLINE}</p>
    </div>
    """, unsafe_allow_html=True)

# Feature highlights
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown("""
        <div class="feature-box">
            <h3 style="color: #667eea;">📰</h3>
            <h4>Smart Extraction</h4>
            <p style="font-size: 0.9rem;">Intelligently scrapes article content from any blog URL</p>
        </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
        <div class="feature-box">
            <h3 style="color: #764ba2;">🤖</h3>
            <h4>AI Summary</h4>
            <p style="font-size: 0.9rem;">GPT-4 creates engaging, natural podcast scripts</p>
        </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
        <div class="feature-box">
            <h3 style="color: #667eea;">🎧</h3>
            <h4>Natural Voice</h4>
            <p style="font-size: 0.9rem;">Premium text-to-speech with human-like quality</p>
        </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown("""
        <div class="feature-box">
            <h3 style="color: #764ba2;">⚡</h3>
            <h4>Instant Results</h4>
            <p style="font-size: 0.9rem;">Get your podcast in under 60 seconds</p>
        </div>
    """, unsafe_allow_html=True)

# Sidebar with instructions and stats
with st.sidebar:
    st.markdown(f"## 🎯 {APP_NAME}")
    st.markdown("---")
    
    
    st.markdown("---")
    st.markdown("### 🎤 TTS Settings")
    
    # Add TTS engine selection
    tts_engine = st.selectbox(
        "Text-to-Speech Engine",
        ["Auto (Best Available)", "ElevenLabs (Premium)", "Edge TTS (Free)", "Offline TTS"],
        help="Auto will try ElevenLabs first, then fallback to free alternatives"
    )
    
    voice_speed = st.slider("Speaking Speed", 0.5, 2.0, 1.0)
    voice_pitch = st.slider("Voice Pitch", -20, 20, 0)
    
    st.markdown("---")
    st.markdown("### 📊 Session Stats")
    if 'podcast_count' not in st.session_state:
        st.session_state.podcast_count = 0
    
    st.markdown(f"""
        <div class="stats-card">
            <h4>🎙️ Podcasts Created</h4>
            <h2 style="color: #667eea;">{st.session_state.podcast_count}</h2>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### 🔧 System Status")
    azure_status = "🟢 Connected" if AZURE_OPENAI_KEY else "🔴 Not configured"
    
    # Check ElevenLabs API key validity
    if ELEVENLABS_API_KEY and ELEVENLABS_API_KEY != "YOUR_KEY_HERE":
        try:
            test_resp = requests.get(
                "https://api.elevenlabs.io/v1/user",
                headers={"xi-api-key": ELEVENLABS_API_KEY},
                timeout=5
            )
            if test_resp.status_code == 200:
                eleven_status = "🟢 Connected"
            else:
                eleven_status = "🟡 Invalid Key (Using Fallback)"
        except:
            eleven_status = "🟡 Unknown (Using Fallback)"
    else:
        eleven_status = "🟡 Not configured (Using Fallback)"
    
    st.markdown(f"**Azure AI:** {azure_status}")
    st.markdown(f"**ElevenLabs:** {eleven_status}")
    
    if "🟡" in eleven_status:
        st.info("💡 Free TTS alternatives will be used automatically")

# Main content area
st.markdown("---")
st.markdown("### 📝 Enter Your Blog Article Link")

# URL input with better styling
url = st.text_input("🔗 Enter Blog URL", placeholder="https://example.com/article", help="Paste the full URL of the blog post you want to convert")
max_chars = st.slider("Max Article Length (characters)", 5000, 25000, 10000, step=1000, help="Limit the amount of text to process from the article")
# Generate button
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    generate_button = st.button("🎙️ Generate Podcast", use_container_width=True)

# Process generation
if generate_button:
    if not url.strip():
        st.warning("⚠️ Please enter a blog URL first.")
    else:
        # Create progress container
        progress_container = st.container()
        with progress_container:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Step 1: Scraping
            status_text.text("📰 Extracting article content...")
            progress_bar.progress(25)
            article_text, page_title = scrape_blog(url, max_chars)
            
            if not article_text:
                st.error("❌ Failed to extract content from the URL. Please check the URL and try again.")
            else:
                # Step 2: Summarizing
                status_text.text("🤖 Creating podcast script with AI...")
                progress_bar.progress(50)
                
                summary = summarize_with_azure_openai(article_text)
                
                if not summary:
                    st.error("❌ Failed to generate podcast script.")
                else:
                    # Add intro and outro if selected
                    # if include_intro:
                    #     summary = f"Welcome to today's podcast! {summary}"
                    # if include_outro:
                    #     summary = f"{summary} Thanks for listening!"
                    
                    # Step 3: Generating audio
                    status_text.text("🎧 Converting to audio...")
                    progress_bar.progress(75)
                    
                    safe_name = create_safe_filename(url, page_title)
                    filename = os.path.join(SAVE_DIR, f"{safe_name}.mp3")
                    
                    # Choose TTS engine based on sidebar selection
                    if tts_engine == "Edge TTS (Free)":
                        ok = edge_tts_fallback(summary, filename)
                    elif tts_engine == "Offline TTS":
                        ok = pyttsx3_fallback(summary, filename)
                    elif tts_engine == "ElevenLabs (Premium)":
                        ok = elevenlabs_tts(summary, filename)
                    else:  # Auto
                        ok = elevenlabs_tts(summary, filename)
                    
                    if ok and os.path.exists(filename):
                        # Step 4: Complete
                        status_text.text("✅ Podcast generated successfully!")
                        progress_bar.progress(100)
                        
                        # Update counter
                        st.session_state.podcast_count += 1
                        
                        # Success message with balloons
                        st.balloons()
                        st.success("🎉 Your podcast is ready!")
                        
                        # Display results
                        result_container = st.container()
                        with result_container:
                            if page_title:
                                  # Clean the title - remove author, date, and source information
                                clean_title = page_title
                                
                                # Remove common patterns like "| by author | date | source"
                                import re
                                # Remove everything after the first | character
                                if '|' in clean_title:
                                    clean_title = clean_title.split('|')[0].strip()
                                
                                # Remove everything after " - " if it contains a domain/source
                                if ' - ' in clean_title:
                                    parts = clean_title.split(' - ')
                                    # Keep only the first part (actual title)
                                    clean_title = parts[0].strip()
                                
                                # Display only the clean article title
                                st.markdown(f"### 📖 {clean_title}")
                            
                            
                            # Single column layout - just audio player and download
                            st.markdown("#### 🎧 Listen to Your Podcast")
                            with open(filename, "rb") as f:
                                audio_bytes = f.read()
                            st.audio(audio_bytes, format="audio/mpeg")
                            
                            # Download button
                            st.download_button(
                                label=f"⬇️ Download: {safe_name}.mp3",
                                data=audio_bytes,
                                file_name=f"{safe_name}.mp3",
                                mime="audio/mpeg",
                                use_container_width=False
                            )
                            
                            # Show script in expander
                            with st.expander("📄 View Podcast Script"):
                                st.text_area("", summary, height=200, disabled=True)
                    else:
                        st.error("❌ Audio generation failed. Please check your settings or try a different TTS engine.")

