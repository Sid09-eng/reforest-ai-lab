# Microclimate run manifest

- Source: `ccnr_microclimate_data.Rdata`
- SHA-256: `673a82f38dd4ed5b2d0ce21c27eafd21ea68ef0655465a2c83092fc1eb3cbebb`
- Rows: 1,002,949 raw; 1,002,899 hard-cleaned; 920,216 analysis-screened.
- The primary EDA and modelling dataset excludes review-flagged rows; sensitivity outputs compare it with the hard-cleaned tier.
- Seed: 42. Classification uses chronological 60/20/20; regression reports separate LOSO site-transfer and chronological results.

See `reproducibility_manifest.json` for split boundaries, feature lists, label rules, model choices, metrics and exact output paths.
