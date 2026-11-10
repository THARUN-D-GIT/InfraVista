# InfraVista — Historical Urban-Growth Methodology

**Module:** P4 — AI/ML and Future Infrastructure Planning  
**Version:** 1.0.0  
**Status:** Proposed — pending methodology, data and team approval

## 1. Objective

Develop a reproducible method for identifying historical built-up expansion within the InfraVista study areas.

Satellite-derived built-up change will be the primary evidence. Existing P3 infrastructure indicators will provide supporting spatial context.

The methodology is intended to establish where and how mapped built-up areas have changed over time. It does not independently establish population growth, infrastructure shortage or investment priority.

## 2. Proposed data sources

Candidate sources include:

- **Sentinel-2:** Multispectral imagery for built-up and land-cover classification.
- **Landsat:** Historical multispectral imagery for longer-term comparisons.
- **GHSL:** Global Human Settlement Layer products for historical built-up information and independent contextual comparison.

Before selecting a source, document:

- Observation dates and temporal coverage.
- Spatial resolution and coordinate reference system.
- Seasonal comparability.
- Cloud and NoData information.
- Data access and licensing conditions.
- Study-area coverage and classification limitations.

No source is approved merely because it is listed here.

## 3. Observation selection

At least two chronological observations are required:

- T0: Earlier observation.
- T1: Later observation.

Both observations must represent the same study area and use comparable seasons, spatial resolution, coordinate reference systems and classification methodology.

A common valid-data mask must be constructed for pixel-level comparisons. Pixels that are cloudy, unobserved or invalid in either observation must be excluded from the change calculation.

## 4. Image preprocessing

The proposed preprocessing workflow is:

1. Acquire imagery for both observation dates.
2. Verify source metadata and usage rights.
3. Apply documented cloud and shadow masking.
4. identify and exclude NoData pixels.
5. Reproject to an approved common CRS.
6. Align both observations to a common spatial grid.
7. Clip imagery to the approved study-area boundary.
8. Verify raster dimensions, pixel alignment and valid-data coverage.
9. Prepare comparable inputs for built-up classification.

Resampling must be selected according to the data type. Categorical classifications require nearest-neighbour resampling; continuous imagery requires an appropriate documented method.

The proposed P3 processing CRS must not be treated as approved until the relevant project team confirms it.

## 5. Built-up classification

Each observation must produce a documented built-up classification:

- 1: Built-up.
- 0: Non-built-up.
- NoData: Invalid or unobserved.

The classification method has not yet been selected.

Potential methods include:

- Spectral-index and threshold-based classification.
- Supervised machine-learning classification.
- Existing validated built-up products.

The selected approach must use documented training or threshold criteria and an accuracy assessment.

Classification uncertainty must be considered when interpreting apparent change.

## 6. Historical-growth indicators

### 6.1 Built-up area

Total mapped built-up area within the valid observation.

Area is calculated from the number of built-up pixels and their ground area.

### 6.2 New built-up area

Area classified as non-built-up at T0 and built-up at T1.

This represents mapped built-up gain.

### 6.3 Built-up area loss

Area classified as built-up at T0 and non-built-up at T1.

This represents mapped built-up loss and does not independently explain its cause.

### 6.4 Net built-up change

Difference between the built-up area at T1 and T0.

### 6.5 Percentage change

Percentage difference relative to the earlier built-up area.

This indicator must not be calculated when the earlier built-up area is zero.

All indicators must use comparable valid-data coverage. The reporting unit is square kilometres unless otherwise specified.

## 7. Spatial development patterns

The following patterns are proposed for a later analytical stage:

- **Infill:** New built-up development within or surrounded by previously developed areas.
- **Edge expansion:** New built-up development adjoining existing built-up areas.
- **Leapfrog development:** New built-up patches spatially separated from previous built-up areas.
- **Fragmentation:** Changes in the size, arrangement and connectivity of built-up patches.

These patterns must not be classified until neighbourhood distances, connectivity rules and minimum patch sizes have been formally defined.

## 8. Supporting P3 infrastructure evidence

P3 indicators may be spatially compared with detected built-up expansion:

- Healthcare and education facility counts.
- Road-density indicators.
- Transit-related facility indicators.
- Waterway density and water-area share.

These indicators describe mapped infrastructure features, not complete inventories or service capacity.

OSM `accessed_at` records data retrieval time, not the historical date when a feature was constructed or became operational.

Consequently, current OSM infrastructure data cannot independently establish historical infrastructure growth.

Existing OSM rights status remains `review_required`; applicable use and redistribution must be cleared before publication.

## 9. Infrastructure demand assessment

Historical built-up change may help identify areas requiring further investigation.

However, sector-specific demand assessment requires additional evidence:

**Healthcare**
- Population distribution and growth.
- Facility capacity.
- Travel time and service areas.

**Education**
- School-age population.
- Enrolment.
- Facility capacity.
- Travel time.

**Transport**
- Population and employment distribution.
- Traffic demand.
- Network connectivity.
- Travel time.

**Water**
- Population and water demand.
- Drainage completeness.
- Rainfall and flood history.
- Elevation.
- Water supply and sanitation coverage.

Built-up expansion alone must not be reported as an infrastructure shortage.

## 10. Accuracy and quality assessment

Before accepting results, assess:

- Classification accuracy using independent reference samples.
- Confusion matrix and relevant class-specific metrics.
- Cloud and NoData exclusion.
- Common valid-data coverage.
- Raster alignment and spatial consistency.
- Sensitivity to classification thresholds.
- Uncertainty in detected gain and loss.

The report must disclose data gaps and uncertainty.

## 11. Reproducibility and reporting

Each analysis run should preserve:

- Source and product identifiers.
- Observation dates.
- Processing and classification parameters.
- CRS and spatial resolution.
- Masking and resampling methods.
- Software and method versions.
- Input and output checksums where available.
- Classification accuracy and valid-data coverage.

Reports must distinguish observed results from assumptions and proposed interpretations.

## 12. Current implementation status

| Component | Status |
|---|---|
| Indicator specification | Draft created |
| Imagery metadata readiness validator | Implemented |
| Historical imagery pair | Not available |
| Raster preprocessing | Not implemented |
| Built-up classification | Not selected |
| Change detection | Not implemented |
| Spatial growth-pattern analysis | Not implemented |
| Infrastructure demand assessment | Future stage |
| Independent P6 validation | Pending |

## 13. Interpretation safeguards

InfraVista must not:

- Claim observed growth without valid raster analysis.
- Interpret missing imagery as no growth.
- Treat current OSM retrieval dates as historical construction dates.
- Treat mapped facility counts as service capacity.
- Claim infrastructure shortage without demand and capacity evidence.
- Present exploratory clusters as investment priorities.
- Claim independent validation before P6 review.

**Current conclusion:** InfraVista has a proposed, reproducible framework for historical built-up change analysis. Actual growth measurement remains pending suitable historical imagery, approved methodology and raster-level validation.