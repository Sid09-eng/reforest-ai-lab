# Reproducibility environment

The verified notebook run used:

- macOS
- Python 3.10.5 through the `week5-python` Jupyter kernel
- R 4.5.2 and `Rscript` to read `ccnr_microclimate_data.Rdata`
- JupyterLab 4.5.4 as the notebook runner
- Python packages pinned in `requirements.txt`

The RData loader uses base R only; no additional R packages are required. The Python process calls:

```text
Rscript --vanilla -e <conversion code> ccnr_microclimate_data.Rdata <temporary.csv>
```

The temporary CSV is deleted after loading. The supplied RData file is read-only and its SHA-256 checksum is recorded in `outputs/redesigned/reproducibility_manifest.json`.

To register an equivalent Python environment as a Jupyter kernel after installing the requirements:

```bash
python3 -m ipykernel install --user --name week5-python --display-name "Python 3.10 (Week 5)"
```
