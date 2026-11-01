# 📦 Unified Inventory Control Tower

A unified inventory management and control tower solution that brings together inventory across stores, warehouses, and online channels while accounting for reservations, safety stock, and in-transit stock.

## 🚀 Project Setup and Installation

Follow the instructions below to clone and run this project on your local system.

### 1. Prerequisites

Make sure the following software is installed:

- Python 3.10 or above
- Git
- Git Large File Storage (Git LFS)
- Visual Studio Code (recommended)

### 2. Install Git LFS

This project uses **Git LFS (Large File Storage)** to store large CSV datasets and other large files.

Git LFS is required to download the actual dataset files when cloning the repository.

Download and install Git LFS:

https://git-lfs.com/

After installation, open a terminal and execute:

```bash
git lfs install
```

Verify the installation:

```bash
git lfs version
```

### 3. Clone the GitHub Repository

Clone the project using:

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
```

Navigate to the project directory:

```bash
cd unified_inventory
```

### 4. Download Large Dataset Files Using Git LFS

After cloning the repository, download all large files managed by Git LFS:

```bash
git lfs pull
```

This command downloads the actual CSV datasets and other large files required by the application.

Verify the downloaded Git LFS files:

```bash
git lfs ls-files
```

**Important:** Without Git LFS, large datasets may appear as pointer files instead of their actual contents. Make sure Git LFS is installed and `git lfs pull` completes successfully before running the application.

### 5. Create a Python Virtual Environment

Create a virtual environment:

```bash
py -m venv .venv
```

Activate the virtual environment:

```bash
.venv\Scripts\activate
```

### 6. Install Project Dependencies

Install all required Python packages:

```bash
pip install -r requirements.txt
```

### 7. Validate the Datasets

Run the validation script to verify the datasets and inventory data:

```bash
python validation/validate.py
```

### 8. Run Automated Test Cases

Execute the test suite:

```bash
python -m pytest -q
```

### 9. Launch the Streamlit Application

Start the Inventory Control Tower dashboard:

```bash
streamlit run app/dashboard.py
```

The application will open in your default web browser.

If it does not open automatically, visit:

```text
http://localhost:8501
```

---

## 📋 Complete Commands (Windows PowerShell)

After installing Git, Git LFS, and Python, execute the following commands in order:

```powershell
# Initialize Git LFS
git lfs install

# Clone the repository
git clone YOUR_GITHUB_REPOSITORY_URL

# Navigate to the project folder
cd unified_inventory

# Download all large datasets
git lfs pull

# Create Python virtual environment
py -m venv .venv

# Activate virtual environment
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Validate datasets
python validation/validate.py

# Run automated tests
python -m pytest -q

# Launch the Streamlit application
streamlit run app/dashboard.py
```

## 🛠️ Technologies Used

- Python
- Pandas
- NumPy
- Streamlit
- Plotly
- FastAPI
- Uvicorn
- Pytest
- Git and Git LFS

## 📂 Project Components

- **Inventory Dashboard:** Unified inventory visibility.
- **Data Validation:** Dataset validation and consistency checks.
- **Inventory Management:** Inventory balances, movements, and reservations.
- **Replenishment:** Safety stock and replenishment rules.
- **Exception Management:** Identification of inventory anomalies and mismatches.
- **API:** FastAPI-based application endpoints.
- **Automated Testing:** Pytest-based acceptance and validation tests.

## 📌 Important Notes

1. Git LFS must be installed before downloading the large datasets.
2. Run `git lfs pull` after cloning to download the actual dataset files.
3. Do not delete or modify the required CSV datasets.
4. Install all dependencies using `requirements.txt`.
5. Run validation and automated tests before launching the application.
6. Ensure sufficient Git LFS storage and bandwidth quota is available to download all project datasets.

## 👨‍💻 Running the Application

Once all installation and validation steps are completed, execute:

```bash
streamlit run app/dashboard.py
```

The Unified Inventory Control Tower dashboard will be available at `http://localhost:8501`.