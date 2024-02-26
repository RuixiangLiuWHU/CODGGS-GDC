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

crs = CRS.from_proj4("+proj=isea +ellps=WGS84")
extent = [-20015625.00, -15011718.75, 20015625.00, 15011718.75]
# tms = morecantile.TileMatrixSet.custom(extent=extent, crs=crs, matrix_scale=[4, 3])
tms = morecantile.TileMatrixSet.custom(extent = extent, crs=crs)


cog_translate(
    r"D:\组内项目\DGGS-Cube计算优化\DGGS\data\cogtest_2_different_landsat\landsat_a.tif",
    r"D:\组内项目\DGGS-Cube计算优化\DGGS\data\cogtest_2_different_landsat\landsat_a_ISEA.tif",
    cog_profile,
    web_optimized=True,
    tms=tms,
    overview_level=0,
    # zoom_level=zoom_level,
    # aligned_levels=4,
    # additional_cog_metadata={
    #     "rhealpix:tile_format": "rHEALPix",
    #     "rhealpix:north_square": north_square,
    #     "rhealpix:south_square": south_square,
    #     "rhealpix:lon_0": lon_0,
    #     "rhealpix:N_side": N_side,
    # },
)

# print(morecantile.tms.get("WebMercatorQuad"))
