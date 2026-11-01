$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
streamlit run app/dashboard.py
