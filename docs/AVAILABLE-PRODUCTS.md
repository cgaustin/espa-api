## Output Product Availability By Input Type
### Level 1 Data
|  | Original Level 1 Data | Original Level 1 Metadata | Customized Level 1 Data |
|:------------- |:------------- |:------------- |:------------- |
| Landsat 4 TM | :heavy_check_mark: | :heavy_check_mark: |:heavy_check_mark:|
| Landsat 5 TM | :heavy_check_mark: | :heavy_check_mark: |:heavy_check_mark:|
| Landsat 7 ETM+ | :heavy_check_mark: | :heavy_check_mark: |:heavy_check_mark:|
| Landsat 8 OLI | :heavy_check_mark: | :heavy_check_mark: |:heavy_check_mark:|
| Landsat 8 TIRS | :heavy_check_mark: | :heavy_check_mark: |:heavy_check_mark:|
| Landsat 8 OLITIRS | :heavy_check_mark: | :heavy_check_mark: |:heavy_check_mark:|
| MODIS 09A1  | :heavy_check_mark: | :heavy_check_mark: |:heavy_check_mark:|
| MODIS 09GA  | :heavy_check_mark: | :heavy_check_mark: |:heavy_check_mark:|
| MODIS 09GQ  | :heavy_check_mark: | :heavy_check_mark: |:heavy_check_mark:|
| MODIS 09Q1  | :heavy_check_mark: | :heavy_check_mark: |:heavy_check_mark:|
| MODIS 13A1  | :heavy_check_mark: | :heavy_check_mark: |:heavy_check_mark:|
| MODIS 13A2  | :heavy_check_mark: | :heavy_check_mark: |:heavy_check_mark:|
| MODIS 13A3  | :heavy_check_mark: | :heavy_check_mark: |:heavy_check_mark:|
| MODIS 13Q1  | :heavy_check_mark: | :heavy_check_mark: |:heavy_check_mark:|

### ESPA CDR/ECV Outputs
|  | TOA | SR | BT | LST | DSWE |
|:------------- |:------------- |:------------- |:------------- |:------------- |:------------- |
| Landsat 4 TM | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: |
| Landsat 5 TM | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: |
| Landsat 7 ETM+ | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: |
| Landsat 8 OLI | :heavy_check_mark: | :x: | :x: | :heavy_check_mark: | :heavy_check_mark: |
| Landsat 8 TIRS | :x: | :x: |:heavy_check_mark:| :x: | :x: |
| Landsat 8 OLITIRS | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: |
| MODIS 09A1  | :x: | :x: | :x: | :x: | :x: |
| MODIS 09GA  | :x: | :x: | :x: | :x: | :x: |
| MODIS 09GQ  | :x: | :x: | :x: | :x: | :x: |
| MODIS 09Q1  | :x: | :x: | :x: | :x: | :x: |
| MODIS 13A1  | :x: | :x: | :x: | :x: | :x: |
| MODIS 13A2  | :x: | :x: | :x: | :x: | :x: |
| MODIS 13A3  | :x: | :x: | :x: | :x: | :x: |
| MODIS 13Q1  | :x: | :x: | :x: | :x: | :x: |

### ESPA Spectral Indices
|  | NDVI | EVI | SAVI | MSAVI | NDMI | NBR | NBR2 |
|:------------- |:------------- |:------------- |:------------- |:------------- |:------------- |:------------- | :------------- |
| Landsat 4 TM | :heavy_check_mark: | :heavy_check_mark: |:heavy_check_mark:| :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: |
| Landsat 5 TM | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: |
| Landsat 7 ETM+ | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark:| :heavy_check_mark:| :heavy_check_mark: |
| Landsat 8 OLI | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: |
| Landsat 8 TIRS | :x: | :x: | :x: | :x: | :x: | :x:| :x: |
| Landsat 8 OLITIRS | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: |
| MODIS 09A1 | :x: | :x: | :x: | :x: | :x: | :x: | :x: |
| MODIS 09GA | :x: | :x: | :x: | :x: | :x: | :x: | :x: |
| MODIS 09GQ | :x: | :x: | :x: | :x: | :x: | :x: | :x: |
| MODIS 09Q1  | :x: | :x: | :x: | :x: | :x: | :x: | :x: |
| MODIS 13A1  | :x: | :x: | :x: | :x: | :x: | :x: | :x: |
| MODIS 13A2  | :x: | :x: | :x: | :x: | :x: | :x: | :x: |
| MODIS 13A3  | :x: | :x: | :x: | :x: | :x: | :x: | :x: |
| MODIS 13Q1  | :x: | :x: | :x: | :x: | :x: | :x: | :x: |

### Notes
Statistics and plotting are available for all ESPA output products.

MODIS products are not generally available for additional processing levels as they have already been processed to a level beyond level 1 by the datasource: MODIS 09 series is at surface reflectance and the 13 series is NDVI/EVI.


##UPDATED VALUES - 1/21/16
##Update TIRS - 1/22/16
####olitirs8
- sourcemetadata
- l1
- toa
- bt
- cloud
- sr
- sr_ndvi
- sr_evi
- sr_savi
- sr_msavi
- sr_ndmi
- sr_nbr
- sr_nbr2
- stats

####oli8
- sourcemetadata
- l1
- toa
- cloud (coming in March 2016 release)
- stats

####tirs8
- bt
- source_metadata

####etm7
- sourcemetadata
- l1
- toa
- bt
- cloud
- sr
- lst (restricted to staff only)
- swe (restricted to staff only)
- sr_ndvi
- sr_evi
- sr_savi
- sr_msavi
- sr_ndmi
- sr_nbr
- sr_nbr2
- stats

####tm4
- sourcemetadata
- l1
- toa
- bt
- cloud
- sr
- swe (restricted to staff only)
- sr_ndvi
- sr_evi
- sr_savi
- sr_msavi
- sr_ndmi
- sr_nbr
- sr_nbr2
- stats

####tm5
- sourcemetadata
- l1
- toa
- bt
- cloud
- sr
- lst (restricted to staff only)
- swe (restricted to staff only)
- sr_ndvi
- sr_evi
- sr_savi
- sr_msavi
- sr_ndmi
- sr_nbr
- sr_nbr2
- stats


####mod09a1
- l1
- stats

####mod09ga
- l1
- stats

####mod09gq
- l1
- stats

####mod09q1
- l1
- stats

####myd09a1
- l1
- stats

####myd09ga
- l1
- stats

####myd09gq
- l1
- stats

####myd09q1
- l1
- stats

####myd13a1
- l1
- stats

####myd13a2
- l1
- stats

####myd13a3
- l1
- stats

####myd13q1
- l1
- stats

####myd13a1
- l1
- stats

####myd13a2
- l1
- stats

####myd13a3
- l1
- stats

####myd13q1
- l1
- stats

