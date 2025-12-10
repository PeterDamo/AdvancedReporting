import streamlit as st
import pandas as pd
from thefuzz import fuzz

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="SAP Smart Reporter", layout="wide")

# --- 1. CLASSI E FUNZIONI DI BACKEND ---

class DataSourceManager:
    def __init__(self):
        if 'data_store' not in st.session_state:
            st.session_state.data_store = {} # Dizionario: {'nome_tabella': dataframe}
        if 'metadata' not in st.session_state:
            st.session_state.metadata = {}   # Dizionario: {'nome_tabella': {'dominio': '...', 'alias': '...'}}

    def add_dataframe(self, name, df, domain, alias):
        st.session_state.data_store[name] = df
        st.session_state.metadata[name] = {'domain': domain, 'alias': alias}

    def get_data(self, name):
        return st.session_state.data_store.get(name)

    def get_all_tables(self):
        return st.session_state.metadata

# Funzione simulata per SAP (Sostituire con hdbcli reale)
def fetch_sap_cds_view(view_name):
    # Dati finti per demo
    data = {
        'BillingDocument': ['90001', '90002', '90003'],
        'CustomerID': ['C100', 'C200', 'C100'],
        'Amount': [1000, 500, 750],
        'Currency': ['EUR', 'EUR', 'USD']
    }
    return pd.DataFrame(data)

# Funzione per suggerire Join (Smart Logic)
def suggest_join_keys(df1, df2):
    cols1 = df1.columns.tolist()
    cols2 = df2.columns.tolist()
    suggestions = []
    
    for c1 in cols1:
        for c2 in cols2:
            # Usa Levenshtein distance per trovare similarità
            ratio = fuzz.ratio(c1.lower(), c2.lower())
            if ratio > 80: # Se sono simili all'80%
                suggestions.append((c1, c2, ratio))
    
    # Ordina per similarità
    suggestions.sort(key=lambda x: x[2], reverse=True)
    return suggestions

# --- 2. INTERFACCIA UTENTE (UI) ---

def main():
    st.title("📊 SAP S/4HANA & Excel Smart Reporter")
    manager = DataSourceManager()

    # --- SIDEBAR: INGESTION DATI ---
    with st.sidebar:
        st.header("1. Data Ingestion")
        
        # A. Caricamento Excel
        uploaded_file = st.file_uploader("Carica Excel Esterno", type=['xlsx', 'csv'])
        if uploaded_file:
            excel_name = st.text_input("Nome Tabella Excel", "Budget_Esterno")
            excel_domain = st.selectbox("Dominio Excel", ["Finance", "Sales", "HR"])
            if st.button("Carica Excel"):
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                manager.add_dataframe(excel_name, df, excel_domain, excel_name)
                st.success(f"Caricato {excel_name}")

        st.divider()

        # B. Connessione SAP (Simulata)
        sap_view = st.text_input("Nome CDS View SAP", "I_BillingDocument")
        sap_domain = st.selectbox("Dominio SAP", ["Sales", "Logistics", "Finance"])
        if st.button("Connetti a SAP"):
            df_sap = fetch_sap_cds_view(sap_view)
            manager.add_dataframe(sap_view, df_sap, sap_domain, sap_view)
            st.success(f"Importata {sap_view}")

    # --- MAIN AREA: DEFINIZIONE JOIN ---
    st.header("2. Data Modeling & Join")
    
    tables = manager.get_all_tables()
    if len(tables) < 2:
        st.info("Carica almeno due tabelle (es. SAP e Excel) per iniziare il join.")
        return

    col1, col2 = st.columns(2)
    with col1:
        table_left = st.selectbox("Tabella Sinistra (Left)", list(tables.keys()))
    with col2:
        table_right = st.selectbox("Tabella Destra (Right)", [t for t in tables.keys() if t != table_left])

    # Smart Suggestion
    df_L = manager.get_data(table_left)
    df_R = manager.get_data(table_right)
    
    suggestions = suggest_join_keys(df_L, df_R)
    
    st.subheader("🔗 Configurazione Join")
    
    if suggestions:
        st.markdown(f"**💡 L'AI suggerisce:** Join tra `{suggestions[0][0]}` e `{suggestions[0][1]}`")
        default_idx_L = list(df_L.columns).index(suggestions[0][0])
        default_idx_R = list(df_R.columns).index(suggestions[0][1])
    else:
        default_idx_L = 0
        default_idx_R = 0

    c1, c2, c3 = st.columns(3)
    key_left = c1.selectbox("Campo Chiave Sinistra", df_L.columns, index=default_idx_L)
    join_type = c2.selectbox("Tipo di Join", ["inner", "left", "right", "outer"])
    key_right = c3.selectbox("Campo Chiave Destra", df_R.columns, index=default_idx_R)

    if st.button("Esegui Join"):
        try:
            # Esecuzione del Merge
            result_df = pd.merge(df_L, df_R, left_on=key_left, right_on=key_right, how=join_type)
            st.session_state['last_result'] = result_df
            st.success("Join eseguito con successo!")
        except Exception as e:
            st.error(f"Errore nel join: {e}")

    # --- AREA: REPORTING & ANALISI ---
    if 'last_result' in st.session_state:
        st.divider()
        st.header("3. Reporting Dinamico")
        
        df_res = st.session_state['last_result']

        # Filtri Dinamici
        with st.expander("🛠 Opzioni Filtri e Raggruppamento"):
            filter_col = st.selectbox("Filtra per colonna:", ["Nessuno"] + list(df_res.columns))
            if filter_col != "Nessuno":
                unique_vals = df_res[filter_col].unique()
                selected_vals = st.multiselect(f"Valori per {filter_col}", unique_vals, default=unique_vals)
                df_res = df_res[df_res[filter_col].isin(selected_vals)]
            
            # Group By opzionale
            groupby_col = st.selectbox("Raggruppa per (Somma metriche):", ["Nessuno"] + list(df_res.columns))

        # Calcolo aggregazioni se richiesto
        if groupby_col != "Nessuno":
            # Seleziona solo colonne numeriche per la somma
            numeric_cols = df_res.select_dtypes(include=['number']).columns
            df_display = df_res.groupby(groupby_col)[numeric_cols].sum().reset_index()
        else:
            df_display = df_res

        # Visualizzazione Tabella
        st.dataframe(df_display, use_container_width=True)

        # Download
        csv = df_display.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Scarica Report CSV", csv, "report.csv", "text/csv")

if __name__ == "__main__":
    main()