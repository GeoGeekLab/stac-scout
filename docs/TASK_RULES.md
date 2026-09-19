# Task rules

STAC Scout's task registry contains conservative defaults for common geospatial analysis goals. These rules are decision support, not universal scientific prescriptions.

Each profile separates:

- **required measurements**: the minimum default inputs Scout is willing to promote to hard request constraints
- **preferred measurements**: useful additions that should not exclude otherwise valid datasets
- **temporal strategy**: whether the task is static, single-window, before/after, or time-series
- **processing preferences**: semantic preferences such as surface reflectance or DEM products
- **masks**: quality information that is useful when the source product exposes it

Every profile has a stable `rule_id`, rationale, and source list. `TaskAdvice.derivations` records which rule caused each change to a request.

## Initial profiles

### Vegetation condition

Default: optical, red + NIR required, SWIR1 preferred.

Basis: NDVI and related vegetation-condition methods rely on the contrast between red absorption and near-infrared reflectance.

Sources:

- https://www.usgs.gov/special-topics/remote-sensing-phenology/science/ndvi-foundation-remote-sensing-phenology
- https://eros.usgs.gov/earthshots/ndvi

### Wildfire impact

Default: optical, NIR + SWIR2 required, before/after comparison.

Basis: NBR uses NIR and SWIR, and differenced NBR compares pre-fire and post-fire observations.

Sources:

- https://www.usgs.gov/landsat-missions/landsat-normalized-burn-ratio
- https://burnseverity.cr.usgs.gov/ravg/background-products-applications

### Flood extent

Default: SAR, before/after comparison. VV and VH are preferences, not hard requirements.

Basis: SAR is useful through cloud cover and at night. Polarization suitability depends on the sensor, scene, land cover, and processing workflow, so Scout does not impose one polarization universally.

Sources:

- https://appliedsciences.nasa.gov/get-involved/training/english/ask-nasa-arset-radar-remote-sensing-flood-monitoring
- https://appliedsciences.nasa.gov/what-we-do/disasters/disasters-activations/hawaii-floods-march-2026

### Surface water

Default: optical, green + SWIR1 required, NIR preferred.

Basis: USGS work found the green/SWIR normalized-difference form to provide a comparatively stable threshold for surface-water delineation.

Sources:

- https://www.usgs.gov/node/97553
- https://www.usgs.gov/centers/eros/science/usgs-eros-archive-vegetation-monitoring-eviirs-global-ndwi

### Snow cover

Default: optical, green + SWIR1 required.

Basis: NDSI uses green and SWIR1 to distinguish snow from common land-surface endmembers.

Source:

- https://www.usgs.gov/landsat-missions/normalized-difference-snow-index

### Terrain

Default: elevation data, static temporal strategy.

Basis: terrain derivatives require an elevation surface; a DEM represents topographic elevation on a regular grid.

Source:

- https://www.usgs.gov/faqs/what-difference-between-lidar-data-and-a-digital-elevation-model-dem

## Heuristic profiles

`land_cover_change` and `urban_change` currently encode broad multispectral defaults rather than a single canonical index. Their requirements are intentionally simple and should be refined as the evaluation corpus grows. They must not be interpreted as claims that one band set is universally optimal.

## Rule behavior

Task advice never overwrites an explicit user data type or task preference. Conflicts are returned in `notes`.

Before/after and time-series strategies do not invent dates. Missing comparison windows or sampling strategy are returned in `follow_up_requirements`.

The registry is packaged as `stac_scout/data/tasks.toml` so rules remain inspectable and versioned independently of model prompts.
