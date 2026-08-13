#!/bin/bash
# ============================================================
# A1 AI System — Ollama Setup Script
# Run this on the Mac Mini BEFORE starting Docker containers.
# ============================================================

set -e

echo "=== A1 AI System: Ollama Model Setup ==="
echo ""

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama not found. Installing..."
    curl -fsSL https://ollama.com/install.sh | sh
    echo "✅ Ollama installed."
else
    echo "✅ Ollama already installed."
fi

# Start Ollama server if not running
if ! pgrep -x "ollama" > /dev/null; then
    echo "Starting Ollama server..."
    ollama serve &
    sleep 3
fi

echo ""
echo "=== Downloading AI Models ==="
echo "This will download ~35 GB total. Please wait..."
echo ""

# 1. Qwen 2.5 32B (Q4_K_M) — Complex agents (Lawyer, Financier, QA)
echo "[1/5] Downloading Qwen 2.5 32B (main LLM for complex tasks)..."
ollama pull qwen2.5:32b

# 2. Llama 3.1 8B (Q4_K_M) — Simple agents (Router, SLA, Secretary, etc.)
echo "[2/5] Downloading Llama 3.1 8B (lightweight LLM for simple tasks)..."
ollama pull llama3.1:8b

# 3. LLaVA 7B — Vision agent (safety photo analysis)
echo "[3/5] Downloading LLaVA 7B (Vision model for photo analysis)..."
ollama pull llava:7b

# 4. Whisper Large v3 — Speech-to-text (via faster-whisper, not Ollama)
echo "[4/5] Whisper will be installed via Python package (faster-whisper)."
echo "       Skipping Ollama download for Whisper."

# 5. nomic-embed-text — Embeddings for RAG
echo "[5/5] Downloading nomic-embed-text (embeddings for RAG)..."
ollama pull nomic-embed-text

echo ""
echo "=== Verifying Models ==="
ollama list

echo ""
echo "=== Testing Models ==="
echo "Testing Llama 3.1 8B..."
echo "Привет, ответь одним словом: работаешь?" | ollama run llama3.1:8b

echo ""
echo "✅ All models downloaded and verified!"
echo ""
echo "=== Memory Usage Estimate ==="
echo "  Qwen 2.5 32B:     ~22 GB"
echo "  Llama 3.1 8B:      ~5 GB"
echo "  LLaVA 7B:           ~5 GB"
echo "  nomic-embed-text:  ~0.3 GB"
echo "  ─────────────────────────"
echo "  Peak total:        ~32 GB (models only)"
echo ""
echo "Mac Mini 64 GB: ✅ Sufficient (15+ GB free for OS and services)"
echo ""
echo "=== Next Steps ==="
echo "1. Copy .env.example to .env and fill in your values"
echo "2. Run: docker compose up -d"
echo "3. Run: docker compose exec backend alembic upgrade head"
echo "4. Start the Telegram bot: it will connect automatically"
