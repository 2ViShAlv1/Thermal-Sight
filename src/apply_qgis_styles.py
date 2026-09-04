"""
QGIS ke liye rang-roop (style) seedha GeoPackage ke ANDAR likh deta hai.

Kyun zaroori: bina style ke QGIS saare points ek hi rang aur ek hi size
mein dikhata hai - to 5 factory wale sources baaki 6,000 mein kho jaate
hain. Style lag jane par factory bade LAAL dots mein alag dikhti hai.

Style GeoPackage ke andar likhne ka faayda: file kholte hi apne aap lag
jaati hai. Alag .qml file load karne ki zaroorat nahi.

DHYAN DO: step3_persistence.py dobara chalane par sources.gpkg naye
sire se banti hai aur style mit jaati hai. Tab ye script phir chala dena.

Chalane ka tareeka (ise venv se NAHI, system python se chalana hai,
kyunki QGIS apne python ke saath aata hai):

    PYTHONPATH=/usr/lib/python3/dist-packages QT_QPA_PLATFORM=offscreen \
        python3 src/apply_qgis_styles.py
"""
import sys
from pathlib import Path

try:
    from qgis.core import (QgsApplication, QgsVectorLayer, QgsSymbol,
                           QgsRendererCategory, QgsCategorizedSymbolRenderer,
                           QgsProperty, QgsSymbolLayer)
    from qgis.PyQt.QtGui import QColor
except ImportError:
    print("QGIS ka python nahi mila. Aise chalao:")
    print("  PYTHONPATH=/usr/lib/python3/dist-packages QT_QPA_PLATFORM=offscreen \\")
    print("      python3 src/apply_qgis_styles.py")
    sys.exit(1)

PROCESSED = Path(__file__).resolve().parent.parent / "data" / "processed"

# har persistence_tier ka rang, size, aur naam
TIER_STYLE = [
    ("EPISODIC",   "#264653", 1.6, "EPISODIC - ek baar ki aag"),
    ("OTHER",      "#f77f00", 2.6, "OTHER - beech ka"),
    ("PERSISTENT", "#d00000", 5.0, "PERSISTENT - factory (saal bhar chali)"),
]

# din vs raat
DAYNIGHT_STYLE = [
    (0, "#e9c46a", "DIN ka detection"),
    (1, "#1d3557", "RAAT ka detection"),
]

# final classification - web dashboard (web/src/lib/theme.jsx) ke rangon
# se HUBAHU milte hain, taaki QGIS mein aur browser mein ek hi source
# ek hi rang ka dikhe
LABEL_STYLE = [
    ("INDUSTRIAL",  "#2a78d6", "Industrial / Mining"),
    ("FOREST_FIRE", "#1baf7a", "Forest fire"),
    ("AGRI_BURN",   "#eb6834", "Crop residue burning"),
    ("UNSURE",      "#898781", "Needs review"),
]


def make_category(layer, value, color, size, label, size_expression=None):
    """Ek category (yani ek rang wala group) banata hai."""
    symbol = QgsSymbol.defaultSymbol(layer.geometryType())
    marker = symbol.symbolLayer(0)
    marker.setColor(QColor(color))
    marker.setStrokeColor(QColor("#ffffff"))
    marker.setStrokeWidth(0.2)
    symbol.setSize(size)
    symbol.setOpacity(0.85)

    if size_expression:
        # dot ka size data se aayega - jitni baar dikha, utna bada dot
        marker.setDataDefinedProperty(
            QgsSymbolLayer.PropertySize,
            QgsProperty.fromExpression(size_expression),
        )
    return QgsRendererCategory(value, symbol, label)


def style_layer(gpkg_name, attribute, spec, size_expr_for=None, size_expr_all=None):
    """Ek gpkg file ko rang lagao aur style usi file ke andar save kar do.

    size_expr_for: sirf PERSISTENT (sources.gpkg) jaisi EK category pe size
                    expression - baaki categories apni fixed size rakhti hain.
    size_expr_all: HAR category pe wahi size expression (predictions.gpkg
                    ke liye - detection count sabhi classes mein maayne
                    rakhta hai, sirf ek mein nahi).
    """
    path = PROCESSED / gpkg_name
    if not path.exists():
        print(f"  SKIP {gpkg_name} - file nahi mili")
        return

    layer = QgsVectorLayer(str(path), path.stem, "ogr")
    if not layer.isValid():
        print(f"  SKIP {gpkg_name} - QGIS ise khol nahi paya")
        return

    categories = []
    for value, color, *rest in spec:
        if len(rest) == 2:                 # (size, label)
            size, label = rest
        else:                              # sirf (label)
            size, label = 1.4, rest[0]
        if size_expr_all:
            expr = size_expr_all
        else:
            expr = size_expr_for if value == size_expr_for_value(size_expr_for, value) else None
        categories.append(make_category(layer, value, color, size, label, expr))

    layer.setRenderer(QgsCategorizedSymbolRenderer(attribute, categories))
    # chhote dots pehle, bade upar - warna factory chhup jayegi
    layer.renderer().setOrderByEnabled(True)

    # useAsDefault=True -> file kholte hi ye style apne aap lag jayegi
    layer.saveStyleToDatabase(f"{path.stem}_style", f"auto style ({attribute})",
                              True, "")
    print(f"  OK   {gpkg_name}  ->  '{attribute}' ke hisaab se rang")


def size_expr_for_value(expr, value):
    """Size expression sirf PERSISTENT pe lagani hai, baaki pe nahi."""
    return "PERSISTENT" if expr else None


def main():
    QgsApplication.setPrefixPath("/usr", True)
    app = QgsApplication([], False)
    app.initQgis()

    print("QGIS styles lagaye ja rahe hain...")
    style_layer("sources.gpkg", "persistence_tier", TIER_STYLE,
                size_expr_for='scale_linear("n_detections", 10, 101, 4, 9)')
    style_layer("features.gpkg", "is_night", DAYNIGHT_STYLE)
    # predictions.gpkg - asli output, "label" column se (INDUSTRIAL/
    # FOREST_FIRE/AGRI_BURN/UNSURE). Ye wahi file hai jo API export
    # karti hai, isliye ye style QGIS mein raw GeoJSON dekhne ke
    # dard ka seedha jawab hai.
    style_layer("predictions.gpkg", "label", LABEL_STYLE,
                size_expr_all='scale_linear("n_detections", 1, 3968, 2, 8)')

    app.exitQgis()
    print("\nAb QGIS mein files dobara kholo - rang apne aap lag jayenge.")
    print("(Agar layer pehle se khuli hai to use hata kar dobara add karo.)")


if __name__ == "__main__":
    main()
