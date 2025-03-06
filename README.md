# ComfyPack

ComfyPack is a web application that helps manage and process ComfyUI workflows. It automatically handles custom node dependencies and model file management for your ComfyUI projects.

## Features

- Upload and process ComfyUI workflow files
- Automatic custom node repository management
- Model file detection and downloading
- Real-time progress updates
- Modern web interface with TailwindCSS

## Prerequisites

- Python 3.8 or higher
- Node.js 16 or higher
- `uv` for Python package management
- `pnpm` for Node.js package management

## Installation

1. Install `uv` if you haven't already:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Install `pnpm` if you haven't already:
```bash
curl -fsSL https://get.pnpm.io/install.sh | sh -
```

3. Clone the repository:
```bash
git clone https://github.com/lxe/comfypack.git
cd comfypack
```

4. Create and activate a Python virtual environment using `uv`:
```bash
uv venv
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate  # On Windows
```

5. Install Python dependencies:
```bash
uv pip install -r requirements.txt
```

6. Install Node.js dependencies:
```bash
pnpm install
```

## Running the Application

1. Build the CSS assets:
```bash
pnpm run build:css
```

2. Start the development server with hot-reloading:
```bash
pnpm run watch
```

This will start both:
- The FastAPI server at http://localhost:8000
- TailwindCSS watcher for automatic CSS rebuilding

## Development

- `pnpm run watch:css` - Watch and rebuild CSS files
- `pnpm run watch:server` - Run the FastAPI server with hot-reload
- `pnpm run watch` - Run both watchers concurrently

## License

MIT