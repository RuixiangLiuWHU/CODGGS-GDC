import os
import pathlib
import sys
import tempfile
import warnings
from contextlib import ExitStack, contextmanager
from typing import Any, Dict, List, Literal, Optional, Sequence, TextIO, Tuple, Union

import click
import morecantile
import rasterio
from rasterio.enums import ColorInterp
from rasterio.enums import Resampling as ResamplingEnums
from rasterio.env import GDALVersion
from rasterio.io import DatasetReader, DatasetWriter, MemoryFile
from rasterio.rio.overview import get_maximum_overview_level
from rasterio.shutil import copy
from rasterio.vrt import WarpedVRT

from rio_cogeo import models, utils
from rio_cogeo.errors import IncompatibleOptions

IN_MEMORY_THRESHOLD = int(os.environ.get("IN_MEMORY_THRESHOLD", 10980 * 10980))

@contextmanager
def TemporaryRasterFile(dst_path: Union[str, pathlib.PurePath], suffix: str = ".tif"):
    """Create temporary file."""
    # For local file we should create temporary file in the same directory
    tmpdir = (
        pathlib.Path(dst_path).parent
        if pathlib.Path(dst_path).parent.is_dir()
        else None
    )
    fileobj = tempfile.NamedTemporaryFile(dir=tmpdir, suffix=suffix, delete=False)
    fileobj.close()
    try:
        yield fileobj
    finally:
        os.remove(fileobj.name)

# RasterIO() resampling method.
# ref: https://gdal.org/api/raster_c_api.html#_CPPv418GDALRIOResampleAlg
RIOResampling = Literal[
    "nearest",
    "bilinear",
    "cubic",
    "cubic_spline",
    "lanczos",
    "average",
    "mode",
    "gauss",
    "rms",
]

# WarpKernel resampling method.
# ref: https://gdal.org/api/gdalwarp_cpp.html#_CPPv4N14GDALWarpKernel9eResampleE
WarpResampling = Literal[
    "nearest",
    "bilinear",
    "cubic",
    "cubic_spline",
    "lanczos",
    "average",
    "mode",
    "sum",
    "rms",
]

def cog_translate(  # noqa: C901
    source: Union[str, pathlib.PurePath, DatasetReader, DatasetWriter, WarpedVRT],
    dst_path: Union[str, pathlib.PurePath],
    dst_kwargs: Dict,
    indexes: Optional[Sequence[int]] = None,
    nodata: Optional[Union[str, int, float]] = None,
    dtype: Optional[str] = None,
    add_mask: bool = False,
    overview_level: Optional[int] = None,
    overview_resampling: RIOResampling = "nearest",
    web_optimized: bool = False,
    tms: Optional[morecantile.TileMatrixSet] = None,
    zoom_level_strategy: str = "auto",
    zoom_level: Optional[int] = None,
    aligned_levels: Optional[int] = None,
    resampling: WarpResampling = "nearest",
    in_memory: Optional[bool] = None,
    config: Optional[Dict] = None,
    allow_intermediate_compression: bool = False,
    forward_band_tags: bool = False,
    forward_ns_tags: bool = False,
    quiet: bool = False,
    progress_out: Optional[TextIO] = None,
    temporary_compression: str = "DEFLATE",
    colormap: Optional[Dict] = None,
    additional_cog_metadata: Optional[Dict] = None,
    use_cog_driver: bool = False,
):
    """
    Create Cloud Optimized Geotiff.

    Parameters
    ----------
    source : str, PathLike object or rasterio.io.DatasetReader
        A dataset path, URL or rasterio.io.DatasetReader object.
        Will be opened in "r" mode.
    dst_path : str or PathLike object
        An output dataset path or or PathLike object.
        Will be opened in "w" mode.
    dst_kwargs: dict
        Output dataset creation options.
    indexes : tuple or int, optional
        Raster band indexes to copy.
    nodata, int, optional
        Overwrite nodata masking values for input dataset.
    dtype: str, optional
        Overwrite output data type. Default will be the input data type.
    add_mask, bool, optional
        Force output dataset creation with a mask.
    overview_level : int, optional (default: None)
        COGEO overview (decimation) level. By default, inferred from data size.
    overview_resampling : str, optional (default: "nearest")
        RasterIO Resampling algorithm for overviews
    web_optimized: bool, optional (default: False)
        Create web-optimized cogeo.
    tms: morecantile.TileMatrixSet, optional (default: "WebMercatorQuad")
        TileMatrixSet to use for reprojection, resolution and alignment.
    zoom_level_strategy: str, optional (default: auto)
        Strategy to determine zoom level (same as in GDAL 3.2).
        LOWER will select the zoom level immediately below the theoretical computed non-integral zoom level, leading to subsampling.
        On the contrary, UPPER will select the immediately above zoom level, leading to oversampling.
        Defaults to AUTO which selects the closest zoom level.
        ref: https://gdal.org/drivers/raster/cog.html#raster-cog
    zoom_level: int, optional.
        Zoom level number (starting at 0 for coarsest zoom level). If this option is specified, `--zoom-level-strategy` is ignored.
    aligned_levels: int, optional.
        Number of overview levels for which GeoTIFF tile and tiles defined in the tiling scheme match.
        Default is to use the maximum overview levels. Note: GDAL use number of resolution levels instead of overview levels.
    resampling : str, optional (default: "nearest")
        Warp Resampling algorithm.
    in_memory: bool, optional
        Force processing raster in memory (default: process in memory if small)
    config : dict
        Rasterio Env options.
    allow_intermediate_compression: bool, optional (default: False)
        Allow intermediate file compression to reduce memory/disk footprint.
        Note: This could reduce the speed of the process.
        Ref: https://github.com/cogeotiff/rio-cogeo/issues/103
    forward_band_tags:  bool, optional
        Forward band tags to output bands.
        Ref: https://github.com/cogeotiff/rio-cogeo/issues/19
    forward_ns_tags:  bool, optional
        Forward namespaces tags to output dataset.
    quiet: bool, optional (default: False)
        Mask processing steps.
    progress_out: TextIO, optional
        Output progress steps to alternative text buffer. Quiet must be False.
    temporary_compression: str, optional
        Compression used for the intermediate file, default is deflate.
    colormap: dict, optional
        Overwrite or add a colormap to the output COG.
    additional_cog_metadata: dict, optional
        Additional dataset metadata to add to the COG.
    use_cog_driver: bool, optional (default: False)
        Use GDAL COG driver if set to True. COG driver is available starting with GDAL 3.1.

    """
    tms = tms or morecantile.tms.get("WebMercatorQuad")

    dst_kwargs = dst_kwargs.copy()

    if isinstance(indexes, int):
        indexes = (indexes,)

    config = config or {}
    with rasterio.Env(**config):
        with ExitStack() as ctx:
            if isinstance(source, (DatasetReader, DatasetWriter, WarpedVRT)):
                src_dst = source
            else:
                src_dst = ctx.enter_context(rasterio.open(source))

            meta = src_dst.meta
            indexes = indexes if indexes else src_dst.indexes
            nodata = nodata if nodata is not None else src_dst.nodata
            dtype = dtype if dtype else src_dst.dtypes[0]
            alpha = utils.has_alpha_band(src_dst)
            mask = utils.has_mask_band(src_dst)

            if colormap and len(indexes) > 1:
                raise IncompatibleOptions(
                    "Cannot add a colormap for multiple bands data."
                )

            if not add_mask and (
                (nodata is not None or alpha)
                and dst_kwargs.get("compress", "").lower() == "jpeg"
            ):
                warnings.warn(
                    "Nodata/Alpha band will be translated to an internal mask band.",
                )
                add_mask = True
                indexes = (
                    utils.non_alpha_indexes(src_dst)
                    if len(indexes) not in [1, 3]
                    else indexes
                )

            tilesize = min(int(dst_kwargs["blockxsize"]), int(dst_kwargs["blockysize"]))

            vrt_params = {
                "add_alpha": True,
                "dtype": dtype,
                "width": src_dst.width,
                "height": src_dst.height,
                "resampling": ResamplingEnums[resampling],
            }

            if nodata is not None:
                vrt_params.update(
                    {"nodata": nodata, "add_alpha": False, "src_nodata": nodata}
                )

            if alpha:
                vrt_params.update({"add_alpha": False})

            if web_optimized:
                wo_params = utils.get_web_optimized_params(
                    src_dst,
                    zoom_level_strategy=zoom_level_strategy,
                    zoom_level=zoom_level,
                    aligned_levels=aligned_levels,
                    tms=tms,
                )
                vrt_params.update(**wo_params)

            with WarpedVRT(src_dst, **vrt_params) as vrt_dst:
                meta = vrt_dst.meta
                meta["count"] = len(indexes)

                if add_mask:
                    meta.pop("nodata", None)
                    meta.pop("alpha", None)

                if (
                    dst_kwargs.get("photometric", "").upper() == "YCBCR"
                    and meta["count"] == 1
                ):
                    warnings.warn(
                        "PHOTOMETRIC=YCBCR not supported on a 1-band raster"
                        " and has been set to 'MINISBLACK'"
                    )
                    dst_kwargs["photometric"] = "MINISBLACK"

                meta.update(**dst_kwargs)
                meta.pop("compress", None)
                meta.pop("photometric", None)

                if allow_intermediate_compression:
                    meta["compress"] = temporary_compression

                if in_memory is None:
                    in_memory = vrt_dst.width * vrt_dst.height < IN_MEMORY_THRESHOLD

                if in_memory:
                    tmpfile = ctx.enter_context(MemoryFile())
                    tmp_dst = ctx.enter_context(tmpfile.open(**meta))
                else:
                    tmpfile = ctx.enter_context(TemporaryRasterFile(dst_path))
                    tmp_dst = ctx.enter_context(
                        rasterio.open(tmpfile.name, "w", **meta)
                    )

                # Transfer color interpolation
                if len(indexes) == 1 and (
                    vrt_dst.colorinterp[indexes[0] - 1] is not ColorInterp.palette
                ):
                    tmp_dst.colorinterp = [ColorInterp.gray]
                else:
                    tmp_dst.colorinterp = [vrt_dst.colorinterp[b - 1] for b in indexes]

                if colormap:
                    if tmp_dst.colorinterp[0] is not ColorInterp.palette:
                        tmp_dst.colorinterp = [ColorInterp.palette]
                        warnings.warn(
                            "Dataset color interpretation was set to `Palette`"
                        )
                    tmp_dst.write_colormap(1, colormap)

                elif tmp_dst.colorinterp[0] is ColorInterp.palette:
                    try:
                        tmp_dst.write_colormap(1, vrt_dst.colormap(1))
                    except ValueError:
                        warnings.warn(
                            "Dataset has `Palette` color interpretation"
                            " but is missing colormap information"
                        )

                wind = list(tmp_dst.block_windows(1))

                if not quiet:
                    click.echo("Reading input: {}".format(source), err=True)

                fout = ctx.enter_context(open(os.devnull, "w")) if quiet else sys.stderr
                if quiet is False and progress_out:
                    fout = progress_out

                with click.progressbar(wind, file=fout, show_percent=True) as windows:  # type: ignore
                    for _, w in windows:
                        matrix = vrt_dst.read(window=w, indexes=indexes)
                        tmp_dst.write(matrix, window=w)

                        if add_mask or mask:
                            # Cast mask to uint8 to fix rasterio 1.1.2 error (ref #115)
                            mask_value = vrt_dst.dataset_mask(window=w).astype("uint8")
                            tmp_dst.write_mask(mask_value, window=w)

                if overview_level is None:
                    overview_level = get_maximum_overview_level(
                        vrt_dst.width, vrt_dst.height, minsize=tilesize
                    )

                if not quiet and overview_level:
                    click.echo("Adding overviews...", err=True)

                overviews = [2**j for j in range(1, overview_level + 1)]
                tmp_dst.build_overviews(overviews, ResamplingEnums[overview_resampling])

                if not quiet:
                    click.echo("Updating dataset tags...", err=True)

                for i, b in enumerate(indexes):
                    tmp_dst.set_band_description(i + 1, src_dst.descriptions[b - 1])
                    if forward_band_tags:
                        tmp_dst.update_tags(bidx=i + 1, **src_dst.tags(b))

                tags = src_dst.tags()
                tags.update(
                    {
                        "OVR_RESAMPLING_ALG": ResamplingEnums[
                            overview_resampling
                        ].name.upper()
                    }
                )
                if web_optimized:
                    default_zoom = tms.zoom_for_res(
                        max(tmp_dst.res),
                        max_z=30,
                        zoom_level_strategy=zoom_level_strategy,
                    )
                    tags.update(
                        {
                            "TILING_SCHEME_NAME": tms.id or "CUSTOM",
                            "TILING_SCHEME_ZOOM_LEVEL": zoom_level
                            if zoom_level is not None
                            else default_zoom,
                        }
                    )
                    if aligned_levels:
                        tags["TILING_SCHEME_ALIGNED_LEVELS"] = aligned_levels

                if additional_cog_metadata:
                    tags.update(**additional_cog_metadata)

                if forward_ns_tags:
                    namespaces = src_dst.tag_namespaces()
                    for ns in namespaces:
                        if ns in ["DERIVED_SUBDATASETS", "IMAGE_STRUCTURE"]:
                            continue
                        tmp_dst.update_tags(ns=ns, **src_dst.tags(ns=ns))

                tmp_dst.update_tags(**tags)
                tmp_dst._set_all_scales([vrt_dst.scales[b - 1] for b in indexes])
                tmp_dst._set_all_offsets([vrt_dst.offsets[b - 1] for b in indexes])

                if not quiet:
                    click.echo("Writing output to: {}".format(dst_path), err=True)

                if use_cog_driver:
                    if not GDALVersion.runtime().at_least("3.1"):
                        raise Exception(
                            "GDAL 3.1 or above required to use the COG driver."
                        )

                    dst_kwargs["driver"] = "COG"

                    if add_mask and dst_kwargs.get("compress", "") != "JPEG":
                        warnings.warn(
                            "With GDAL COG driver, mask band will be translated to an alpha band."
                        )

                    dst_kwargs["overview_resampling"] = overview_resampling
                    dst_kwargs["warp_resampling"] = resampling
                    dst_kwargs["blocksize"] = tilesize
                    dst_kwargs.pop("blockxsize", None)
                    dst_kwargs.pop("blockysize", None)
                    dst_kwargs.pop("tiled", None)
                    dst_kwargs.pop("interleave", None)
                    dst_kwargs.pop("photometric", None)

                    copy(tmp_dst, dst_path, **dst_kwargs)

                else:
                    copy(tmp_dst, dst_path, copy_src_overviews=True, **dst_kwargs)

