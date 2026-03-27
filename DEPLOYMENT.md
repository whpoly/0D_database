# ZeroDB Deployment

## 1. Current status

This repository is already deployable as a Dash app.

I verified locally that:

- the `web` Conda environment can import `dash`, `crystal_toolkit`, and `pymatgen`
- `python main.py` starts the app successfully
- `http://127.0.0.1:8050/` returns `200`
- `http://127.0.0.1:8050/details?mid=mp-1101228_0D_V2F9` returns `200`

## 2. Files added for deployment

- `.env.example`: runtime and path configuration template
- `gunicorn.conf.py`: production Gunicorn configuration
- `requirements-prod.txt`: Linux production dependencies
- `scripts/run_dev.ps1`: local Windows development entrypoint
- `scripts/run_prod.sh`: Linux production entrypoint
- `deploy/systemd/zerodb.service.example`: systemd service template
- `deploy/nginx/zerodb.conf.example`: Nginx reverse proxy template

## 3. App configuration

`main.py` now supports configuration from `.env` or environment variables.

Supported variables:

- `ZERO_DB_ENV`
- `ZERO_DB_HOST`
- `ZERO_DB_PORT`
- `ZERO_DB_DEBUG`
- `ZERO_DB_DEV_TOOLS_UI`
- `ZERO_DB_DATA_PATH`
- `ZERO_DB_RADIUS_PATH`
- `ZERO_DB_DFT_ROOT_DIR`
- `ZERO_DB_DOS_BS_DIR`

Path values can be absolute paths or paths relative to the repository root.

## 4. Recommended deployment shape

For production, I recommend Linux:

- Ubuntu 22.04 or 24.04
- 2 vCPU
- 4 to 8 GB RAM
- 20 to 40 GB SSD if you deploy only the web app plus `dos_bs`
- 100 GB or more if you also keep the raw DFT folders on the server

The current deployment-friendly data layout is:

- `ZeroDB_test_data.json`
- `atomic_radius.json`
- `dos_bs/`

If `dos_bs/<material_id>/bs.json` and `dos_bs/<material_id>/dos.json` are complete, the app can render BS/DOS without reading the raw VASP folders.

## 5. Local development

### Windows PowerShell

```powershell
Copy-Item .env.example .env
.\scripts\run_dev.ps1
```

### Or with Conda directly

```powershell
conda activate web
python main.py
```

By default, development mode uses:

- `ZERO_DB_ENV=development`
- `ZERO_DB_DEBUG=1`
- `ZERO_DB_PORT=8050`

## 6. Linux production deployment

### Step 1: prepare the server

```bash
sudo mkdir -p /opt/zerodb
sudo chown -R $USER:$USER /opt/zerodb
cd /opt/zerodb
git clone <your-repo-url> .
```

### Step 2: create the environment

```bash
conda env create -f environment.yml
conda activate web
pip install -r requirements-prod.txt
```

### Step 3: create the production `.env`

```bash
cp .env.example .env
```

Then edit `.env` and set at least:

```env
ZERO_DB_ENV=production
ZERO_DB_HOST=127.0.0.1
ZERO_DB_PORT=8050
ZERO_DB_DEBUG=0
ZERO_DB_DEV_TOOLS_UI=0
ZERO_DB_DATA_PATH=ZeroDB_test_data.json
ZERO_DB_RADIUS_PATH=atomic_radius.json
ZERO_DB_DOS_BS_DIR=dos_bs
```

If you still want raw-file fallback, also keep:

```env
ZERO_DB_DFT_ROOT_DIR=ZeroDB_test_data/ZeroDB_test_data
```

### Step 4: test Gunicorn manually

```bash
conda activate web
./scripts/run_prod.sh
```

Then open:

```text
http://127.0.0.1:8050
```

## 7. systemd service

Copy and edit the template:

```bash
sudo cp deploy/systemd/zerodb.service.example /etc/systemd/system/zerodb.service
sudo nano /etc/systemd/system/zerodb.service
```

You must adjust:

- `User`
- `Group`
- `WorkingDirectory`
- `EnvironmentFile`
- `ExecStart`

Then enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable zerodb
sudo systemctl start zerodb
sudo systemctl status zerodb
```

## 8. Nginx

Copy and edit the template:

```bash
sudo cp deploy/nginx/zerodb.conf.example /etc/nginx/sites-available/zerodb
sudo nano /etc/nginx/sites-available/zerodb
sudo ln -s /etc/nginx/sites-available/zerodb /etc/nginx/sites-enabled/zerodb
sudo nginx -t
sudo systemctl reload nginx
```

After that, add HTTPS with Certbot if you are using a public domain.

## 9. What should be deployed

### Smallest web-only deployment

Deploy these:

- `main.py`
- `gunicorn.conf.py`
- `.env`
- `ZeroDB_test_data.json`
- `atomic_radius.json`
- `dos_bs/`
- `requirements.txt`
- `requirements-prod.txt`

### Deployment with raw VASP fallback

Deploy the above plus:

- `ZeroDB_test_data/ZeroDB_test_data/`

## 10. Notes

- `python main.py` is now configuration-driven and suitable for development.
- production should use Gunicorn, not Dash debug mode.
- if you change the BS/DOS cache, regenerate `dos_bs/` before redeploying.
