import streamlit as st
import pandas as pd
import io, os, re, unicodedata
from datetime import datetime, date
from dateutil import tz

# ==========================
# Config
# ==========================
st.set_page_config(page_title="Feria — Registro y Verificación", layout="wide")
DATA_DIR = "data"
INSCRIPCIONES_XLSX = os.path.join(DATA_DIR, "inscripciones.xlsx")
VERIFICACIONES_XLSX = os.path.join(DATA_DIR, "verificaciones.xlsx")

# 
MASTER_COLUMNS = [
    "N°","FECHA DE INGRESO","N° DE DOCUMENTO SIMPLE","ASUNTO","NOMBRES Y APELLIDO","DNI",
    "DOMICILIO","RUBRO","", "UBICACIÓN A SOLICITAR","N° DE CELULAR","PROCEDENTE / IMPROCEDENTE",
    "N° DE CARTA","FECHA DE LA CARTA","FECHA DE NOTIFICACION","PAGO","N° DE RECIBO",
    "N° DE AUTORIZACION","FECHA DE EVENTO","FOLIOS","ARCHIVO","PUESTO"
]

# ==========================
# Utilidades comunes
# ==========================
def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)

def today():
    return datetime.now(tz=tz.tzlocal()).date()

def strip_accents(s: str) -> str:
    if s is None: return ""
    s = unicodedata.normalize("NFD", str(s))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")

def normalize_header(h: str) -> str:
    h = strip_accents(str(h))
    h = h.encode("ascii", "ignore").decode("ascii")
    h = re.sub(r"[^A-Za-z0-9]+", " ", h)
    return " ".join(h.split()).lower()

DATE_FORMATS = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"]

def parse_possible_date(s):
    if s is None or (isinstance(s, float) and pd.isna(s)): return None
    if isinstance(s, datetime): return s.date()
    if isinstance(s, date): return s
    txt = str(s).strip()
    if not txt: return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(txt, fmt).date()
        except ValueError:
            pass
    d = pd.to_datetime(txt, dayfirst=True, errors="coerce")
    return d.date() if pd.notna(d) else None

def format_ddmmyyyy(d: date) -> str:
    return d.strftime("%d/%m/%Y")

def join_event_dates(d1: date, d2: date | None) -> str:
    if d1 and d2:
        return f"{format_ddmmyyyy(d1)} Y {format_ddmmyyyy(d2)}"
    if d1:
        return format_ddmmyyyy(d1)
    return ""

def split_event_dates(raw):
    if raw is None: return []
    text = str(raw).upper().replace(" Y ", " ").replace("Y", " ")
    matches = re.findall(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text)
    fechas = []
    for m in matches:
        d = parse_possible_date(m)
        if d: fechas.append(d)
    fechas = sorted(set(fechas))
    return fechas[:2]

def to_number_maybe(x):
    if pd.isna(x): return None
    s = str(x).strip()
    if not s: return None
    s = s.replace("S/.", "").replace("S/", "").replace("S", "").replace(" ", "")
    if s.count(",") == 1 and s.count(".") == 0:
        s = s.replace(",", ".")
    if s.count(".") > 1:
        s = s.replace(".", "", s.count(".") - 1)
    try:
        return float(s)
    except Exception:
        return None

# ==========================
# Persistencia (Excel)
# ==========================
def load_master() -> pd.DataFrame:
    ensure_dirs()
    if not os.path.exists(INSCRIPCIONES_XLSX):
        # crear archivo vacío con headers
        df = pd.DataFrame(columns=MASTER_COLUMNS)
        df.to_excel(INSCRIPCIONES_XLSX, index=False)
        return df
    return pd.read_excel(INSCRIPCIONES_XLSX)

def save_master(df: pd.DataFrame):
    df.to_excel(INSCRIPCIONES_XLSX, index=False)

def load_verificaciones() -> pd.DataFrame:
    ensure_dirs()
    if not os.path.exists(VERIFICACIONES_XLSX):
        df = pd.DataFrame(columns=[
            "dni","fecha_evento_dia","puesto_codigo",
            "en_puesto_correcto","voucher_ok","observacion","archivo_nombre","timestamp"
        ])
        df.to_excel(VERIFICACIONES_XLSX, index=False)
        return df
    return pd.read_excel(VERIFICACIONES_XLSX)

def save_verificaciones(df: pd.DataFrame):
    df.to_excel(VERIFICACIONES_XLSX, index=False)

# ==========================
# Normalización por día
# ==========================
def normalize_days(df_master: pd.DataFrame) -> pd.DataFrame:
    # Mapear headers a internos
    colmap = {normalize_header(c): c for c in df_master.columns}
    get = lambda friendly: df_master[colmap.get(normalize_header(friendly))]

    # columnas mínimas
    dni = get("DNI").astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    nombre = get("NOMBRES Y APELLIDO").astype(str).str.strip().str.upper()
    rubro = get("RUBRO").astype(str).str.strip().str.upper()
    nro_recibo = get("N° DE RECIBO").astype(str).str.strip()
    monto_pago = get("PAGO").apply(to_number_maybe)
    doc_simple = get("N° DE DOCUMENTO SIMPLE").astype(str).str.strip()
    fecha_ingreso = get("FECHA DE INGRESO").apply(parse_possible_date)
    fecha_evento = get("FECHA DE EVENTO").astype(str)
    puesto = df_master[colmap.get(normalize_header("PUESTO"))] if "PUESTO" in df_master.columns else ""

    rows = []
    for i in range(len(df_master)):
        fechas = split_event_dates(fecha_evento.iloc[i])
        if not fechas:
            # fila sin fecha válida, se ignora en normalizado
            continue
        for d_ev in fechas:
            rows.append({
                "dni": str(dni.iloc[i]),
                "nombre_apellido": nombre.iloc[i],
                "rubro": rubro.iloc[i],
                "nro_recibo": nro_recibo.iloc[i],
                "monto_pago": monto_pago.iloc[i],
                "fecha_evento_dia": d_ev,
                "documento_simple": doc_simple.iloc[i],
                "fecha_ingreso": fecha_ingreso.iloc[i],
                "cubre_dos_dias": (len(fechas) == 2),
                "puesto": puesto.iloc[i] if isinstance(puesto, pd.Series) else ""
            })
    return pd.DataFrame(rows)

# ==========================
# UI — Sidebar
# ==========================
st.sidebar.title("Feria")
mod = st.sidebar.radio("Módulo", ["Registro", "Verificación"], index=0)

# ==========================
# MÓDULO: Registro
# ==========================
if mod == "Registro":
    st.title("Registro de feriantes")
    st.caption("Para inscripciones nuevas o de última hora. Guarda en el Excel maestro.")

    df_master = load_master()

    with st.expander("Importar/actualizar desde un Excel existente (opcional)"):
        up = st.file_uploader("Subir Excel con la misma estructura (se añadirá al maestro)", type=["xlsx"], key="imp_excel")
        if up:
            try:
                df_new = pd.read_excel(up)
                # normaliza columnas faltantes
                for c in MASTER_COLUMNS:
                    if c not in df_new.columns:
                        df_new[c] = ""
                df_new = df_new[MASTER_COLUMNS]
                # concatenar
                df_master = pd.concat([df_master, df_new], ignore_index=True)
                save_master(df_master)
                st.success(f"Importado {len(df_new)} registros.")
            except Exception as e:
                st.error(f"Error al importar: {e}")

    st.subheader("Nueva inscripción")
    with st.form("form_registro", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            fecha_ingreso = st.date_input("Fecha de ingreso", value=today(), format="DD/MM/YYYY")
            documento_simple = st.text_input("N° de documento simple")
            asunto = st.text_input("Asunto", value="")
        with c2:
            nombres = st.text_input("Nombres y Apellido").upper()
            dni = st.text_input("DNI")
            domicilio = st.text_input("Domicilio", value="")
        with c3:
            rubro = st.text_input("Rubro").upper()
            celular = st.text_input("N° de celular", value="")
            puesto = st.number_input("Puesto (solo números)", min_value=1, step=1)

        c4, c5, c6 = st.columns(3)
        with c4:
            pago = st.text_input("Pago (ej. 20, 40)").strip()
            nro_recibo = st.text_input("N° de recibo").strip()
        with c5:
            fecha_evento_1 = st.date_input("Fecha de evento (día 1)", value=today(), format="DD/MM/YYYY")
            dos_dias = st.checkbox("Cubre dos días")
        with c6:
            fecha_evento_2 = st.date_input("Fecha de evento (día 2, opcional)", value=today(), format="DD/MM/YYYY", disabled=not dos_dias)

        obs_cols = st.columns(3)
        with obs_cols[0]:
            procedencia = st.selectbox("Procedente / Improcedente", ["", "PROCEDENTE", "IMPROCEDENTE"])
        with obs_cols[1]:
            ubicacion_sol = st.text_input("Ubicación a solicitar", value="")
        with obs_cols[2]:
            archivo = st.text_input("Archivo (nombre/ref)", value="")

        submitted = st.form_submit_button("Guardar inscripción")

        if submitted:
            # Validaciones básicas
            if not nombres or not dni or not nro_recibo or not pago:
                st.error("Campos obligatorios: Nombres y Apellido, DNI, N° de Recibo y Pago.")
            else:
                # Armar registro alineado a columnas
                next_n = (df_master["N°"].max() + 1) if ("N°" in df_master.columns and pd.api.types.is_numeric_dtype(df_master["N°"])) else 1
                pago_num = to_number_maybe(pago)
                evento = join_event_dates(fecha_evento_1, fecha_evento_2 if dos_dias else None)

                new_row = {
                    "N°": int(next_n),
                    "FECHA DE INGRESO": format_ddmmyyyy(fecha_ingreso),
                    "N° DE DOCUMENTO SIMPLE": documento_simple,
                    "ASUNTO": asunto,
                    "NOMBRES Y APELLIDO": nombres,
                    "DNI": dni,
                    "DOMICILIO": domicilio,
                    "RUBRO": rubro,
                    "": "",
                    "UBICACIÓN A SOLICITAR": ubicacion_sol,
                    "N° DE CELULAR": celular,
                    "PROCEDENTE / IMPROCEDENTE": procedencia,
                    "N° DE CARTA": "",
                    "FECHA DE LA CARTA": "",
                    "FECHA DE NOTIFICACION": "",
                    "PAGO": pago_num if pago_num is not None else pago,
                    "N° DE RECIBO": nro_recibo,
                    "N° DE AUTORIZACION": "",
                    "FECHA DE EVENTO": evento,
                    "FOLIOS": "",
                    "ARCHIVO": archivo,
                    "PUESTO": int(puesto)
                }

                df_master = pd.concat([df_master, pd.DataFrame([new_row])], ignore_index=True)
                save_master(df_master)
                st.success("Inscripción guardada en el maestro.")

    st.subheader("Maestro (últimos 50)")
    st.dataframe(load_master().tail(50), use_container_width=True)

    st.download_button(
        "Descargar maestro.xlsx",
        data=load_master().to_excel(io.BytesIO(), index=False) or io.BytesIO().getvalue(),
        file_name="inscripciones.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ==========================
# MÓDULO: Verificación
# ==========================
else:
    st.title("Verificación en campo")
    st.caption("Normaliza por día, busca por DNI/Nombre y guarda checks.")

    # Cargar maestro y normalizar por día
    df_master = load_master()
    if df_master.empty:
        st.info("Aún no hay inscripciones en el maestro. Registra primero o importa un Excel en el módulo de Registro.")
        st.stop()

    df_days = normalize_days(df_master)

    with st.expander("Normalizado por día (vista previa)"):
        st.dataframe(df_days.sort_values(["fecha_evento_dia","nombre_apellido"]).reset_index(drop=True), use_container_width=True)

    # Cargar verificaciones actuales
    verif = load_verificaciones()

    # Filtros
    c1, c2, c3 = st.columns(3)
    fechas_disp = sorted(df_days["fecha_evento_dia"].dropna().unique().tolist())
    with c1:
        fecha_sel = st.selectbox("Día de feria", options=fechas_disp, format_func=lambda d: pd.to_datetime(d).strftime("%d/%m/%Y"))
    with c2:
        dni_q = st.text_input("Filtrar por DNI (opcional)").strip()
    with c3:
        nom_q = st.text_input("Filtrar por Nombre (opcional)").upper().strip()

    df_dia = df_days[df_days["fecha_evento_dia"] == fecha_sel].copy()
    if dni_q:
        df_dia = df_dia[df_dia["dni"].astype(str).str.contains(dni_q, case=False)]
    if nom_q:
        df_dia = df_dia[df_dia["nombre_apellido"].str.contains(nom_q, case=False)]

    st.caption("Abre cada tarjeta, marca y guarda.")
    for i, r in df_dia.sort_values("nombre_apellido").iterrows():
        header = f"{r['nombre_apellido']} — DNI {r['dni']} — Recibo {r['nro_recibo']}"
        with st.expander(header):
            cL, cM, cR = st.columns([1,1,2])
            with cL:
                en_puesto = st.checkbox("En puesto correcto", key=f"en_puesto_{i}")
                voucher_ok = st.checkbox("Voucher OK", key=f"voucher_ok_{i}")
            with cM:
              
                puesto_sugerido = str(r.get("puesto") or "")
                puesto_codigo = st.text_input("Número de puesto (opcional)", value=puesto_sugerido, key=f"puesto_{i}")
            with cR:
                obs = st.text_area("Observación", key=f"obs_{i}", height=70)

            up = st.file_uploader("Foto voucher/evidencia (opcional, se guarda solo el nombre)", type=["jpg","jpeg","png","pdf"], key=f"file_{i}")
            archivo_nombre = up.name if up else ""

            if st.button("Guardar verificación", key=f"save_{i}"):
                # upsert por (dni, fecha_evento_dia)
                dni_key = str(r["dni"])
                dia_key = pd.to_datetime(r["fecha_evento_dia"]).date()
                mask = (verif["dni"].astype(str) == dni_key) & (pd.to_datetime(verif["fecha_evento_dia"]).dt.date == dia_key)
                data = {
                    "dni": dni_key,
                    "fecha_evento_dia": dia_key,
                    "puesto_codigo": puesto_codigo.strip(),
                    "en_puesto_correcto": bool(en_puesto),
                    "voucher_ok": bool(voucher_ok),
                    "observacion": obs.strip(),
                    "archivo_nombre": archivo_nombre,
                    "timestamp": datetime.now()
                }
                if mask.any():
                    verif.loc[mask, list(data.keys())] = pd.Series(data)
                else:
                    verif = pd.concat([verif, pd.DataFrame([data])], ignore_index=True)
                save_verificaciones(verif)
                st.success("Verificación guardada.")

    st.subheader("Verificaciones acumuladas")
    st.dataframe(load_verificaciones().sort_values(["fecha_evento_dia","dni"]).reset_index(drop=True), use_container_width=True)

    # Export
    st.subheader("Exportar")
    def to_excel_bytes(sheets: dict) -> bytes:
        bio = io.BytesIO()
        with pd.ExcelWriter(bio, engine="openpyxl") as writer:
            for name, dfx in sheets.items():
                dfx.to_excel(writer, index=False, sheet_name=name[:31])
        bio.seek(0)
        return bio.read()

    cA, cB = st.columns(2)
    with cA:
        csv = load_verificaciones().to_csv(index=False).encode("utf-8")
        st.download_button("Descargar verificaciones.csv", data=csv, file_name="verificaciones.csv", mime="text/csv")
    with cB:
        xls = to_excel_bytes({
            "maestro": load_master(),
            "normalizado_dias": df_days,
            "verificaciones": load_verificaciones()
        })
        st.download_button("Descargar consolidado.xlsx", data=xls, file_name="consolidado_feria.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


