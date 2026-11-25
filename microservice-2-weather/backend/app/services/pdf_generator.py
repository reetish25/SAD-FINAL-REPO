"""
Pure-Python PDF 1.4 Generator for Leafline Weather Service Reports.
Requires no external C libraries or compiled dependencies.
Produces valid, paginated, professionally styled vector PDF documents.
"""

from datetime import datetime, timezone
import io
import zlib


def _escape_pdf_text(text: str) -> str:
    """Escape special characters for PDF text strings."""
    if text is None:
        return ""
    text = str(text)
    # Replace non-ascii chars with clean ascii approximations
    clean = ""
    for ch in text:
        if ch in ('(', ')', '\\'):
            clean += '\\' + ch
        elif ord(ch) < 128:
            clean += ch
        elif ch == '°':
            clean += ' deg '
        elif ch == '–' or ch == '—':
            clean += '-'
        elif ch in ('“', '”'):
            clean += '"'
        elif ch in ('‘', '’'):
            clean += "'"
        else:
            clean += ' '
    return clean


class PDFCanvas:
    """Draws text and graphics onto a single A4 page (595.28 x 841.89 points)."""

    def __init__(self, page_num: int, total_pages: int):
        self.width = 595.28
        self.height = 841.89
        self.page_num = page_num
        self.total_pages = total_pages
        self.ops = []

    def rect(self, x, y, w, h, fill_rgb=None, stroke_rgb=None, line_width=1.0):
        cmd = []
        if line_width != 1.0:
            cmd.append(f"{line_width:.2f} w")
        if fill_rgb:
            r, g, b = fill_rgb
            cmd.append(f"{r:.3f} {g:.3f} {b:.3f} rg")
        if stroke_rgb:
            r, g, b = stroke_rgb
            cmd.append(f"{r:.3f} {g:.3f} {b:.3f} RG")
        cmd.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re")
        if fill_rgb and stroke_rgb:
            cmd.append("B")
        elif fill_rgb:
            cmd.append("f")
        else:
            cmd.append("S")
        self.ops.append(" ".join(cmd))

    def line(self, x1, y1, x2, y2, stroke_rgb=(0.2, 0.2, 0.2), line_width=1.0):
        r, g, b = stroke_rgb
        self.ops.append(f"{line_width:.2f} w {r:.3f} {g:.3f} {b:.3f} RG {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")

    def text(self, x, y, text_str, font="F1", size=10, fill_rgb=(0, 0, 0)):
        r, g, b = fill_rgb
        esc = _escape_pdf_text(text_str)
        self.ops.append(f"BT /{font} {size:.1f} Tf {r:.3f} {g:.3f} {b:.3f} rg {x:.2f} {y:.2f} Td ({esc}) Tj ET")

    def to_stream(self) -> bytes:
        data = "\n".join(self.ops).encode("latin-1", errors="replace")
        return zlib.compress(data)


def generate_weather_service_report(
    organization_name: str,
    organization_id: str,
    date_from: str | None,
    date_to: str | None,
    user_filter: str | None,
    sensor_filter: str | None,
    records: list[dict],
    stats: dict | None = None,
    data_scope: str = 'Sensor Data',
    measurement_filter: str | None = None
) -> bytes:
    """
    Generates a professional, branded Leafline Weather Service PDF report.
    """
    total_records = len(records)
    records_per_page = 22

    # Calculate pagination
    # If 0 records, 1 page
    # Page 1 has header banner, metadata, summary statistics, then table starts
    # Subsequent pages have header continuation, table continuation, and footer
    if total_records <= 14:
        total_pages = 1
    else:
        # Page 1 has room for ~14 records; subsequent pages have room for ~24 records
        remaining = total_records - 14
        total_pages = 1 + (remaining + records_per_page - 1) // records_per_page

    pages: list[PDFCanvas] = []

    # Calculate stats if not provided
    if not stats:
        temps = [r.get('reading_value') or r.get('temperature_c') for r in records if (r.get('reading_value') or r.get('temperature_c')) is not None and ('temp' in (r.get('measurement_type') or '').lower() or r.get('temperature_c') is not None)]
        temps = [t for t in temps if t is not None]
        humids = [r.get('humidity_pct') for r in records if r.get('humidity_pct') is not None]
        rains = [r.get('rainfall_mm') for r in records if r.get('rainfall_mm') is not None]
        users = len({r.get('user_id') for r in records if r.get('user_id')})
        sensors_cnt = len({r.get('device_id') or r.get('sensor_name') for r in records if r.get('device_id') or r.get('sensor_name')})

        stats = {
            'total_readings': total_records,
            'temp_avg': f"{sum(temps)/len(temps):.1f}°C" if temps else "N/A",
            'temp_min_max': f"{min(temps):.1f} - {max(temps):.1f}°C" if temps else "N/A",
            'humidity_avg': f"{sum(humids)/len(humids):.1f}%" if humids else "N/A",
            'rainfall_sum': f"{sum(rains):.1f} mm" if rains else "0.0 mm",
            'unique_users': users,
            'unique_sensors': sensors_cnt
        }

    record_index = 0

    for page_idx in range(1, total_pages + 1):
        canvas = PDFCanvas(page_num=page_idx, total_pages=total_pages)

        # Draw Background Frame & Header
        # Deep forest green top banner: #123c28 -> (0.071, 0.235, 0.157)
        banner_rgb = (0.071, 0.235, 0.157)
        emerald_rgb = (0.086, 0.639, 0.290)
        slate_bg = (0.965, 0.973, 0.965)
        text_dark = (0.09, 0.12, 0.10)
        text_muted = (0.35, 0.40, 0.38)
        border_light = (0.82, 0.86, 0.83)

        # Header banner
        canvas.rect(25, 785, 545.28, 42, fill_rgb=banner_rgb)
        canvas.rect(25, 782, 545.28, 3, fill_rgb=emerald_rgb)

        canvas.text(38, 804, "LEAFLINE", font="F2", size=15, fill_rgb=(1, 1, 1))
        canvas.text(120, 804, "|   Weather Service Report", font="F1", size=13, fill_rgb=(0.85, 0.95, 0.88))
        canvas.text(420, 804, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), font="F1", size=8.5, fill_rgb=(0.75, 0.85, 0.78))

        if page_idx == 1:
            # Metadata Box
            canvas.rect(25, 705, 545.28, 70, fill_rgb=slate_bg, stroke_rgb=border_light, line_width=0.8)
            
            # Left column: Organization Info
            canvas.text(38, 756, f"ORGANIZATION: {organization_name}", font="F2", size=11, fill_rgb=text_dark)
            canvas.text(38, 740, f"Organization ID: {organization_id or 'ORG-UNASSIGNED'}", font="F1", size=9.5, fill_rgb=text_muted)
            canvas.text(38, 725, f"Date Range: {date_from or 'All Available'}  to  {date_to or 'Present'}", font="F1", size=9.5, fill_rgb=text_muted)

            # Right column: Scope & Filter
            canvas.text(320, 756, f"Scope: {data_scope}", font="F2", size=9.5, fill_rgb=text_dark)
            canvas.text(320, 740, f"User Filter: {user_filter or 'All Associated Users'}", font="F1", size=9.5, fill_rgb=text_muted)
            canvas.text(320, 725, f"Sensor: {sensor_filter or 'All Sensors'} | Measurement: {measurement_filter or 'All Parameters'}", font="F1", size=8.2, fill_rgb=text_muted)

            # Summary Statistics Cards
            # 4 mini cards across width: 545.28 pt -> 4 cards of ~130 pt each
            stats_y = 650
            card_w = 127
            card_h = 46
            gap = 12.4
            
            stat_items = [
                ("Total Records", str(stats.get('total_readings', 0)), (0.07, 0.24, 0.16)),
                ("Temp (Avg / Span)", f"{stats.get('temp_avg')} ({stats.get('temp_min_max')})", (0.85, 0.45, 0.1)),
                ("Humidity (Avg)", str(stats.get('humidity_avg', 'N/A')), (0.15, 0.55, 0.8)),
                ("Rainfall Total", str(stats.get('rainfall_sum', '0.0 mm')), (0.1, 0.65, 0.55))
            ]

            for i, (label, val, tint) in enumerate(stat_items):
                cx = 25 + i * (card_w + gap)
                canvas.rect(cx, stats_y, card_w, card_h, fill_rgb=(1, 1, 1), stroke_rgb=border_light, line_width=0.8)
                canvas.rect(cx, stats_y + card_h - 2.5, card_w, 2.5, fill_rgb=tint)
                canvas.text(cx + 8, stats_y + 28, label.upper(), font="F2", size=7, fill_rgb=text_muted)
                canvas.text(cx + 8, stats_y + 12, val, font="F2", size=9.5, fill_rgb=text_dark)

            table_top_y = 635
            max_rows = 14
        else:
            # Continuation page header
            canvas.text(38, 762, f"Report Continued: {organization_name} (ID: {organization_id})", font="F2", size=10, fill_rgb=text_muted)
            canvas.line(25, 755, 570.28, 755, stroke_rgb=border_light, line_width=0.8)
            table_top_y = 745
            max_rows = records_per_page

        # Render Table Header
        th_h = 22
        canvas.rect(25, table_top_y - th_h, 545.28, th_h, fill_rgb=banner_rgb)
        
        # Columns:
        # 1. Date/Time (x=32, w=95)
        # 2. User ID (x=130, w=55)
        # 3. Sensor Name & Model (x=190, w=125)
        # 4. Parameter (x=320, w=95)
        # 5. Value & Unit (x=420, w=75)
        # 6. Farm / Location (x=500, w=65)
        canvas.text(32, table_top_y - 15, "DATE / TIME", font="F2", size=7.5, fill_rgb=(1, 1, 1))
        canvas.text(130, table_top_y - 15, "USER ID", font="F2", size=7.5, fill_rgb=(1, 1, 1))
        canvas.text(190, table_top_y - 15, "SENSOR & MODEL", font="F2", size=7.5, fill_rgb=(1, 1, 1))
        canvas.text(320, table_top_y - 15, "MEASUREMENT", font="F2", size=7.5, fill_rgb=(1, 1, 1))
        canvas.text(420, table_top_y - 15, "VALUE", font="F2", size=7.5, fill_rgb=(1, 1, 1))
        canvas.text(500, table_top_y - 15, "LOCATION", font="F2", size=7.5, fill_rgb=(1, 1, 1))

        # Render Table Rows
        row_y = table_top_y - th_h
        row_h = 20.5
        rows_on_this_page = 0
        current_section = None

        while record_index < total_records and rows_on_this_page < max_rows:
            rec = records[record_index]
            section = rec.get('record_type') or 'SENSOR DATA'
            if section != current_section:
                row_y -= 16
                section_label = 'FORECAST DATA (OPEN-METEO SNAPSHOTS)' if section == 'FORECAST DATA' else 'SENSOR DATA (REGISTERED FIELD READINGS)'
                canvas.rect(25, row_y, 545.28, 15, fill_rgb=(0.91, 0.96, 0.92), stroke_rgb=border_light, line_width=0.4)
                canvas.text(32, row_y + 4, section_label, font="F2", size=7.5, fill_rgb=banner_rgb)
                current_section = section
            row_y -= row_h
            rows_on_this_page += 1
            record_index += 1

            # Alternating background
            if rows_on_this_page % 2 == 0:
                canvas.rect(25, row_y, 545.28, row_h, fill_rgb=(0.97, 0.98, 0.97))
            else:
                canvas.rect(25, row_y, 545.28, row_h, fill_rgb=(1, 1, 1))

            canvas.line(25, row_y, 570.28, row_y, stroke_rgb=(0.90, 0.92, 0.90), line_width=0.5)

            # Format fields
            dt_str = str(rec.get('recorded_at') or rec.get('observed_at') or rec.get('received_at') or '—')
            if 'T' in dt_str:
                dt_str = dt_str.replace('T', ' ')[:16]
            elif len(dt_str) > 16:
                dt_str = dt_str[:16]

            u_id = str(rec.get('user_id') or 'USR1')
            s_name = str(rec.get('sensor_name') or rec.get('device_id') or 'Weather Station')
            s_model = str(rec.get('sensor_model') or rec.get('model') or 'DHT22')
            sensor_full = f"{s_name} ({s_model})"[:24]

            meas_type = str(rec.get('measurement_type') or 'Weather Obs')[:26]

            # Reading value
            val = rec.get('reading_value')
            unit = rec.get('measurement_unit') or ''
            if val is None:
                if rec.get('temperature_c') is not None:
                    val = f"{rec.get('temperature_c'):.1f}°C"
                elif rec.get('humidity_pct') is not None:
                    val = f"{rec.get('humidity_pct'):.0f}%"
                elif rec.get('rainfall_mm') is not None:
                    val = f"{rec.get('rainfall_mm'):.1f} mm"
                else:
                    val = "Recorded"
            else:
                val = f"{val:.1f} {unit}".strip()

            loc = str(rec.get('farm_location') or rec.get('field_id') or 'Field A')[:14]

            canvas.text(32, row_y + 6, dt_str, font="F1", size=8, fill_rgb=text_dark)
            canvas.text(130, row_y + 6, u_id, font="F2", size=8, fill_rgb=emerald_rgb)
            canvas.text(190, row_y + 6, sensor_full, font="F1", size=8, fill_rgb=text_dark)
            canvas.text(320, row_y + 6, meas_type, font="F1", size=7, fill_rgb=text_muted)
            canvas.text(420, row_y + 6, str(val), font="F2", size=8, fill_rgb=text_dark)
            canvas.text(500, row_y + 6, loc, font="F1", size=8, fill_rgb=text_muted)

        if total_records == 0:
            row_y -= 40
            canvas.rect(25, row_y, 545.28, 40, fill_rgb=(0.98, 0.98, 0.98))
            canvas.text(200, row_y + 16, "No historical forecast or sensor records found matching criteria.", font="F1", size=9.5, fill_rgb=text_muted)

        # Footer on every page
        canvas.line(25, 45, 570.28, 45, stroke_rgb=border_light, line_width=0.8)
        canvas.text(25, 32, "Leafline – Weather Service   |   Sunflower Health Intelligence Platform   |   Confidential", font="F1", size=7.5, fill_rgb=text_muted)
        canvas.text(490, 32, f"Page {page_idx} of {total_pages}", font="F2", size=8, fill_rgb=text_dark)

        pages.append(canvas)

    # Assemble complete PDF structure
    return _build_pdf_bytes(pages)


def _build_pdf_bytes(pages: list[PDFCanvas]) -> bytes:
    """Combines canvas pages into a compliant PDF 1.4 byte string."""
    buf = io.BytesIO()
    buf.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    xref_offsets = []
    current_offset = buf.tell()

    # Objects list:
    # 1: Catalog
    # 2: Pages
    # 3: Font F1 (Helvetica)
    # 4: Font F2 (Helvetica-Bold)
    # For each page i (0-based):
    #   Page object: 5 + 2*i
    #   Content object: 6 + 2*i

    num_pages = len(pages)
    total_objects = 4 + 2 * num_pages

    # 1 0 obj: Catalog
    xref_offsets.append(buf.tell())
    buf.write(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

    # 2 0 obj: Pages
    page_refs = " ".join([f"{5 + 2 * i} 0 R" for i in range(num_pages)])
    xref_offsets.append(buf.tell())
    buf.write(f"2 0 obj\n<< /Type /Pages /Kids [{page_refs}] /Count {num_pages} >>\nendobj\n".encode("latin-1"))

    # 3 0 obj: Font F1 (Helvetica)
    xref_offsets.append(buf.tell())
    buf.write(b"3 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>\nendobj\n")

    # 4 0 obj: Font F2 (Helvetica-Bold)
    xref_offsets.append(buf.tell())
    buf.write(b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>\nendobj\n")

    # Pages and contents
    for i, p in enumerate(pages):
        page_obj_num = 5 + 2 * i
        content_obj_num = 6 + 2 * i

        # Page Object
        xref_offsets.append(buf.tell())
        page_dict = (
            f"{page_obj_num} 0 obj\n"
            f"<< /Type /Page /Parent 2 0 R\n"
            f"   /MediaBox [0 0 {p.width:.2f} {p.height:.2f}]\n"
            f"   /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >>\n"
            f"   /Contents {content_obj_num} 0 R\n"
            f">>\nendobj\n"
        )
        buf.write(page_dict.encode("latin-1"))

        # Content Object (FlateDecode compressed)
        compressed_stream = p.to_stream()
        xref_offsets.append(buf.tell())
        content_header = (
            f"{content_obj_num} 0 obj\n"
            f"<< /Length {len(compressed_stream)} /Filter /FlateDecode >>\n"
            f"stream\n"
        ).encode("latin-1")
        buf.write(content_header)
        buf.write(compressed_stream)
        buf.write(b"\nendstream\nendobj\n")

    # Xref Table
    startxref = buf.tell()
    buf.write(f"xref\n0 {total_objects + 1}\n".encode("latin-1"))
    buf.write(b"0000000000 65535 f \n")
    for offset in xref_offsets:
        buf.write(f"{offset:010d} 00000 n \n".encode("latin-1"))

    # Trailer
    trailer = (
        f"trailer\n"
        f"<< /Size {total_objects + 1}\n"
        f"   /Root 1 0 R\n"
        f">>\n"
        f"startxref\n"
        f"{startxref}\n"
        f"%%EOF\n"
    )
    buf.write(trailer.encode("latin-1"))

    return buf.getvalue()
