# Module 00 · Setup

**Time:** about 20 minutes (mostly downloads)

The course needs three things on your Mac: Ollama, three small models, and Python 3.9 or newer. One script checks all of it.

## Steps

**1. Check Ollama.**
```bash
ollama --version
```
You should see a version number. If you see `command not found`, download the Mac app from https://ollama.com/download, open it once, then run this step again.

**2. Download the models (about 3.5 GB total).**
```bash
ollama pull llama3.2:1b && ollama pull llama3.2:3b && ollama pull nomic-embed-text
```
You should see `success` three times.

**3. Check Python.**
```bash
python3 --version
```
You should see `Python 3.9` or higher.

**4. Update your KARMO checkout, which holds the BloomBoss data the labs read.**
```bash
cd ~/KARMO-DEV && git pull
```
You should see `Already up to date.` or a list of updated files.

**5. Run the setup check.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/00-setup && python3 check_setup.py
```
You should see `OK` on every line and `ALL SET. Start Module 1.` Any line marked `FIX` tells you the exact command to run.

## Done when
- [ ] `check_setup.py` prints `ALL SET`
