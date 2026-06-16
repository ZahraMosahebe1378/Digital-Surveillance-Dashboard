# Phase 1

## Goal
Convert messy Ontario epidemiological CSV files into a **common weekly timeline** for downstream LSTM/Transformer training.

## Pipeline
1. Upload CSV
2. Keep only Ontario rows (`province`, `pruid=35`, or Ontario lat/lon bbox)
3. Match locations to major Ontario cities using fuzzy text and/or nearest lat/lon
4. Detect temporal frequency
5. Aggregate to weekly using data-type rules
6. Export CSV

## Weekly rules
- **Hourly air pollution:** weekly mean / max / variance
- **Monthly climate:** forward-fill / interpolate, then weekly
- **Daily mobility:** weekly average
- **Outbreak:** weekly sum
- **Social media / news:** weekly count / sentiment mean / topic frequency
- **Wastewater:** already weekly; standardize city/region/week columns

## Location matching
Matching is **not exact**. The backend uses:
- fuzzy string similarity plus alias/region matching
- nearest-city matching from latitude/longitude when coordinate columns exist

Examples:
- `Toronto` -> Toronto / Greater Toronto Area
- `Peel Region` -> Mississauga or Brampton / Peel Region
- `43.6532, -79.3832` -> Toronto / Greater Toronto Area
- `Greater Sudbury` -> Sudbury / Northern Ontario

Not all major cities need data in every file.
