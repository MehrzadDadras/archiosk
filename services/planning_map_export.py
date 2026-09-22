"""Opt-in report evidence projection; no retrieval, project creation or report store."""
import hashlib
import json
from html import escape
from pathlib import Path

from services import deterministic_spatial as spatial
from services import planning_acceptance as acceptance
from services import planning_visual as visual
from services import document_export

VERSION = "planning-map-export@1"
CAPTION = "ARCHIOSK rendering of official municipal geometry"


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2).encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _rings(g):
    if g.get("type") == "Polygon":
        return g["coordinates"]
    if g.get("type") == "MultiPolygon":
        return [r for p in g["coordinates"] for r in p]
    raise ValueError("Unsupported geometry; no visual exported")


def build(result, *, address):
    """Render the exact retained polygons; reject missing or contradictory bindings.

    The caller supplies the finished governed result, not a browser-posted view.
    Street/base-map imagery is not invented. Full zone extent and north arrow
    provide geographic context; nearby zones absent from retrieval stay absent.
    """
    r = result["retrieval"]
    if not r.get("zone_features_examined"):
        raise ValueError("Split-zone examination unavailable")
    parcel = r["visual_geometry"]["parcel"]
    zones = [z for z in r.get("zone_features", []) if z.get("qualified")]
    if not zones or not r.get("retrieved_at"):
        raise ValueError("Missing zoning evidence/currentness")
    if len(zones) > 8:
        raise ValueError("Report panel zone bound exceeded; no zones omitted")
    panels = visual.panels_for(r, tokens=result.get("spatial_tokens"))
    check = acceptance.evaluate(result, panels=panels)
    if check["state"] not in (acceptance.PASS, acceptance.PASS_WITH_UNRESOLVED_EXCEPTION):
        raise ValueError("Visual acceptance: " + check["state"])
    crs = parcel.get("spatial_reference")
    if crs != "EPSG:3857":
        raise ValueError("Unqualified render CRS")
    for z in zones:
        if not all(z.get(k) is not None for k in ("geometry", "geometry_id", "feature_identifier", "url", "zone_label")):
            raise ValueError("Incomplete feature provenance")
        if z.get("source_crs") != crs or spatial.geometry_hash(z["geometry"]) != z["geometry_id"]:
            raise ValueError("Zoning geometry binding mismatch")
        attributes = z.get("attributes") or {}
        if attributes.get("ZN_STRING") is not None and attributes["ZN_STRING"] != z["zone_label"]:
            raise ValueError("Feature label mismatch")
        if attributes.get("ZN_EXCPTN_NO") is not None and str(attributes["ZN_EXCPTN_NO"]) != str(z.get("exception_identifier")):
            raise ValueError("Feature exception mismatch")
        token = spatial.relate({"crs":crs,"geometry":parcel["geometry"]},
                               {"crs":crs,"geometry":z["geometry"]})
        if token["spatial_relation"] != z.get("spatial_relation"):
            raise ValueError("Spatial relationship mismatch")
    if spatial.geometry_hash(parcel["geometry"]) != parcel.get("geometry_id"):
        raise ValueError("Parcel geometry binding mismatch")
    rings = _rings(parcel["geometry"]) + [ring for z in zones for ring in _rings(z["geometry"])]
    if sum(map(len, rings)) > visual.MAX_PANEL_VERTICES:
        raise ValueError("Render vertex bound exceeded; no simplification")
    extent = visual._extent(rings)
    if not extent or max(extent[2]-extent[0],extent[3]-extent[1]) <= 0:
        raise ValueError("Degenerate extent")
    width=1000; map_size=800
    paths=[]
    colors=["#d9e9f5", "#eee2c5", "#d7ebda", "#e7d8ef"]
    for i,z in enumerate(zones):
        path=" ".join(visual._path(ring,extent,map_size,30) for ring in _rings(z["geometry"]))
        paths.append(f'<path d="{path}" fill="{colors[i%len(colors)]}" stroke="#45647b" stroke-width="2" fill-rule="evenodd"/>')
    path=" ".join(visual._path(ring,extent,map_size,30) for ring in _rings(parcel["geometry"]))
    paths.append(f'<path d="{path}" fill="#f9ad3280" stroke="#a33412" stroke-width="4" fill-rule="evenodd"/>')
    labels=[address, "Subject parcel: orange outline; zoning: blue/alternate fill", "North is up; full retrieved zoning extent; not a survey"]
    labels += [f'{i+1}. {z["zone_label"]} | Exception {z.get("exception_identifier") if z.get("exception_identifier") is not None else "not recorded"}: {z.get("exception_status") or "UNKNOWN"}' for i,z in enumerate(zones)]
    height=900+28*len(labels)
    text="".join(f'<text x="35" y="{40+28*i}" font-size="18">{escape(str(line))}</text>' for i,line in enumerate(labels))
    text += "".join(f'<rect x="10" y="{110+28*i}" width="16" height="16" fill="{colors[i%len(colors)]}" stroke="#45647b"/>' for i in range(len(zones)))
    svg=(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
         f'<rect width="100%" height="100%" fill="white"/><g font-family="sans-serif" fill="#182936">{text}</g>'
         f'<g transform="translate(100,{60+28*len(labels)})">'+"".join(paths)+
         '<text x="740" y="22" font-size="20">N ↑</text></g></svg>')
    import fitz
    with fitz.open(stream=svg.encode(),filetype="svg") as doc:
        png=doc[0].get_pixmap().tobytes("png")
    provenance={"version":VERSION,"caption":CAPTION,"authority":"City of Toronto",
                "address":address,"retrieved_at":r["retrieved_at"],"source_crs":crs,
                "parcel":{k:v for k,v in parcel.items() if k!="geometry"},
                "zones":[{k:v for k,v in z.items() if k!="geometry"} for z in zones],
                "acceptance":check,"retrieval_sha256":sha(encoded(r)),
                "image_sha256":sha(png),"svg_sha256":sha(svg.encode()),
                "context_limit":"Only retrieved polygons; streets and unretained neighbouring zones are not depicted.",
                "source_limitation":visual.LIMITATION}
    caption=f'{CAPTION}. {address}. '+"; ".join(labels[3:])+f'. Relationship: {check["relationship"]}. Retrieved {r["retrieved_at"]}; {crs}. '+provenance["context_limit"]
    return {"png":png,"svg":svg,"provenance":provenance,
            "parcel":parcel,"zones":zones,
            "figure":document_export.ExportFigure("Official Zoning Evidence",png,caption)}


def save_package(destination, result, view, *, address, generated_at):
    """Explicit existing deliverable directory only; never create/guess a project.

    Exclusive writes preserve prior reports. This is an export package, not a
    PlanningReview persistence model or a claim that the live route saved it.
    """
    from services import planning_export
    root=Path(destination)
    if not root.is_dir():
        raise ValueError("An existing authorized report destination is required")
    if view.get("retrieval") != result.get("retrieval"):
        raise ValueError("Report/retrieval mismatch")
    if view.get("identity",{}).get("address") != address:
        raise ValueError("Report/property mismatch")
    # The rendered view must originate from this document, not a separate prose object.
    from services import planning_result_view
    expected=planning_result_view.build_view(result)
    if view != expected:
        raise ValueError("Report/document mismatch")
    asset=build(result,address=address)
    document=planning_export.build_export_document(view, generated_at=generated_at)
    if result.get("fixture_note"):
        document.preamble.insert(0, result["fixture_note"])
    document.figures.append(asset["figure"])
    files={"evidence/zoning-map.png":asset["png"],"evidence/zoning-map.svg":asset["svg"].encode(),
           "evidence/parcel-geometry.json":encoded(asset["parcel"]),
           "evidence/zoning-geometry.json":encoded(asset["zones"]),
           "evidence/provenance.json":encoded(asset["provenance"]),
           "result.json":encoded(result["document"])}
    for fmt in ("pdf","docx"):
        files[planning_export.filename_for(view["identity"],fmt)]=document_export.build(document,fmt).getvalue()
    files["export-manifest.json"]=encoded({"generated_at":generated_at,"version":VERSION,
        "files":{n:sha(b) for n,b in files.items()},"note":"Explicit report export; live route remains ephemeral."})
    if any((root/n).exists() for n in files):
        raise FileExistsError("Report artifacts already exist; choose a new report revision directory")
    for n,b in files.items():
        target=root/n; target.parent.mkdir(parents=True,exist_ok=True)
        with target.open("xb") as f:f.write(b)
        assert sha(target.read_bytes())==sha(b)
    return asset["provenance"]
