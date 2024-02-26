from pyproj import CRS

from COGGenerate.COG_Translate import cog_translate
import morecantile

cog_profile = {
    "driver": "GTiff",
    "interleave": "pixel",
    "tiled": True,
    "blockxsize": 256,
    "blockysize": 256,
    "compress": "DEFLATE",
}

north_square = 1
south_square = 2
lon_0 = 0
N_side = 2

crs = CRS.from_proj4(
    "+proj=rhealpix +ellps=WGS84 +south_square=" + str(south_square) + " +north_square=" + str(
        north_square) + " +lon_0=" + str(lon_0))
extent = [-20015625.00, -15011718.75, 20015625.00, 15011718.75]
tms = morecantile.TileMatrixSet.custom(extent=extent, crs=crs, matrix_scale=[4, 3])

resolution = 30
max_zoom_level = tms.zoom_for_res(30)
print("max_zoom_level: ", max_zoom_level)
for zoom_level in range(0, max_zoom_level + 1):
    cog_translate(
        r"D:\组内项目\DGGS-Cube计算优化\DGGS\data\cogtest_2_different_landsat\landsat_a.tif",
        r"D:\组内项目\DGGS-Cube计算优化\DGGS\data\cogtest_2_different_landsat\landsat_a_rHEALPix_" + str(
            zoom_level) + ".tif",
        cog_profile,
        web_optimized=True,
        tms=tms,
        overview_level=0,
        zoom_level=zoom_level,
        # aligned_levels=4,
        additional_cog_metadata={
            "rhealpix:tile_format": "rHEALPix",
            "rhealpix:north_square": north_square,
            "rhealpix:south_square": south_square,
            "rhealpix:lon_0": lon_0,
            "rhealpix:N_side": N_side,
        },
    )

# print(morecantile.tms.get("WebMercatorQuad"))
