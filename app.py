import streamlit as st
import pandas as pd
from thefuzz import fuzz
import io

# --- CONFIGURAZIONE PAGINA ---
# Non è più necessario forzare il tema qui se usiamo config.toml, ma lasciamo il layout wide
st.set_page_config(page_title="Advanced Smart Reporter", layout="wide")

# --- 1. CLASSI E FUNZIONI DI BACKEND ---

class DataSourceManager:
    """Gestisce l'archiviazione e i metadati di tutti i DataFrame caricati."""
    def __init__(self):
        if 'data_store' not in st.session_state:
            st.session_state.data_store = {}
        if 'metadata' not in st.session_state:
            st.session_state.metadata = {}

    def add_dataframe(self, name, df, domain, alias):
        st.session_state.data_store[name] = df
        st.session_state.metadata[name] = {'domain': domain, 'alias': alias}

    def get_data(self, name):
        return st.session_state.data_store.get(name)

    def get_all_tables(self):
        return st.session_state.metadata

def fetch_sap_cds_view(view_name):
    """Simula l'estrazione dati da una CDS View (sostituire con hdbcli reale)."""
    # Dati finti per demo SAP
    data = {
        'BillingDoc': ['90001', '90002', '90003', '90004'],
        'CustomerID': ['C100', 'C200', 'C100', 'C300'],
        'SalesAmount': [1000.50, 500.20, 750.00, 1200.00],
        'Currency': ['EUR', 'EUR', 'USD', 'EUR']
    }
    return pd.DataFrame(data)

def suggest_join_keys(df1, df2):
    """Suggerisce chiavi di join basate sulla similarità dei nomi di colonna."""
    cols1 = df1.columns.tolist()
    cols2 = df2.columns.tolist()
    suggestions = []
    
    for c1 in cols1:
        for c2 in cols2:
            ratio = fuzz.ratio(c1.lower(), c2.lower())
            if ratio > 80:
                suggestions.append((c1, c2, ratio))
    
    suggestions.sort(key=lambda x: x[2], reverse=True)
    return suggestions

# --- 2. INTERFACCIA UTENTE (UI) ---

def main():
    manager = DataSourceManager()

    st.title("📊 Advanced SAP & Excel Smart Reporter")
    st.caption("Strumento Self-Service BI per la combinazione di dati S/4HANA e sorgenti esterne.")

    # Creazione delle schede di navigazione
    tab_ingestion, tab_modeling, tab_reporting = st.tabs([
        "1. Ingestion & Pre-Processing", 
        "2. Data Modeling & Join", 
        "3. Final Reporting & Analysis"
    ])

    # =========================================================================
    # TAB 1: INGESTION & PRE-PROCESSING
    # =========================================================================
    with tab_ingestion:
        st.header("1. Caricamento Dati e Pulizia")
        
        col_files, col_join = st.columns(2)
        
        with col_files:
            st.subheader("Carica Sorgenti")
            uploaded_files = st.file_uploader("Carica File Excel/CSV (multiplo)", type=['xlsx', 'csv'], accept_multiple_files=True)
            
            sap_view = st.text_input("Nome CDS View SAP (Opzionale)", "I_BillingDoc_Sim")
            if st.button("Carica CDS View"):
                df_sap = fetch_sap_cds_view(sap_view)
                manager.add_dataframe(sap_view, df_sap, "SAP Sales", sap_view)
                st.success(f"Importata CDS View: {sap_view}")

        with col_join:
            st.subheader("Unione Excel e Metadata")
            
            if uploaded_files:
                st.info(f"Caricati {len(uploaded_files)} file. Assegna il nome al risultato per l'unione verticale (Concatenazione).")
                
                # Prende le colonne dal primo file per suggerire l'unione
                try:
                    # Legge il primo file per suggerire la colonna chiave
                    if uploaded_files[0].name.endswith('.xlsx'):
                        temp_df = pd.read_excel(uploaded_files[0])
                    else:
                        temp_df = pd.read_csv(uploaded_files[0])
                        
                    join_col = st.selectbox("Colonna da usare come chiave comune per l'unione verticale", 
                                            ['Nessuna (usa l\'indice)'] + temp_df.columns.tolist(), 
                                            index=0)
                except Exception:
                    st.warning("Impossibile leggere il primo file per suggerire le colonne.")
                    join_col = 'Nessuna (usa l\'indice)'
                
                final_excel_name = st.text_input("Nome Tabella Unita (Excel)", "Dati_Excel_Uniti")
                final_excel_domain = st.selectbox("Dominio Tabella Unita", ["Finance", "Sales", "HR", "Logistics"])

                if st.button("Unisci File Excel"):
                    try:
                        all_excel_dfs = []
                        for uploaded_file in uploaded_files:
                            if uploaded_file.name.endswith('.xlsx'):
                                df = pd.read_excel(uploaded_file)
                            else:
                                df = pd.read_csv(uploaded_file)
                            
                            # Logica di unione condizionale (se la chiave è stata selezionata)
                            if join_col != 'Nessuna (usa l\'indice)' and join_col not in df.columns:
                                st.warning(f"File {uploaded_file.name} ignorato: manca la colonna chiave '{join_col}'.")
                            else:
                                all_excel_dfs.append(df)
                                
                        if all_excel_dfs:
                            result_df = pd.concat(all_excel_dfs, ignore_index=True)
                            manager.add_dataframe(final_excel_name, result_df, final_excel_domain, final_excel_name)
                            st.success(f"Uniti {len(all_excel_dfs)} file in '{final_excel_name}'.")
                        else:
                            st.error("Nessun file Excel è stato unito.")
                    except Exception as e:
                        st.error(f"Errore durante l'unione: {e}")


        st.divider()
        st.subheader("Anteprima, Modifica e Pre-analisi")
        
        current_tables = list(manager.get_all_tables().keys())
        if current_tables:
            selected_table = st.selectbox("Seleziona la tabella da visualizzare/modificare:", current_tables)
            df_preview = manager.get_data(selected_table).copy()

            # Modifica Inline e Filtri
            with st.expander(f"🛠 Modifica, Filtri e Aggregazioni per {selected_table}", expanded=True):
                
                # Modifica Inline (Streamlit Data Editor)
                st.markdown("**Modifica Dati (doppio click):**")
                df_edited = st.data_editor(df_preview, use_container_width=True, key=f"editor_{selected_table}")
                
                if st.button(f"Salva Modifiche per {selected_table}", key=f"save_{selected_table}"):
                    manager.add_dataframe(selected_table, df_edited, 
                                          manager.get_all_tables()[selected_table]['domain'],
                                          manager.get_all_tables()[selected_table]['alias'])
                    st.success(f"Modifiche salvate per {selected_table}.")
                
                st.markdown("---")
                
                # Filtri e Somme (Pre-analisi)
                col_filt, col_sum = st.columns(2)
                df_filtered = df_edited.copy()

                with col_filt:
                    filter_col = st.selectbox("Filtra riga per colonna:", ["Nessuno"] + list(df_edited.columns), key=f"filt_col_{selected_table}")
                    if filter_col != "Nessuno":
                        unique_vals = df_edited[filter_col].unique()
                        selected_vals = st.multiselect(f"Valori da mantenere in {filter_col}", unique_vals, default=unique_vals, key=f"filt_val_{selected_table}")
                        df_filtered = df_edited[df_edited[filter_col].isin(selected_vals)]
                        st.dataframe(df_filtered)

                with col_sum:
                    numeric_cols = df_filtered.select_dtypes(include=['number']).columns
                    sum_col = st.selectbox("Calcola Somma per colonna:", ["Nessuno"] + list(numeric_cols), key=f"sum_col_{selected_table}")
                    if sum_col != "Nessuno":
                        st.metric(f"Totale Filtrato di {sum_col}", f"{df_filtered[sum_col].sum():,.2f}")

        else:
            st.info("Nessuna tabella caricata. Inizia caricando un file Excel o una CDS View.")

    # =========================================================================
    # TAB 2: DATA MODELING & JOIN
    # =========================================================================
    with tab_modeling:
        st.header("2. Data Modeling & Join")
        
        tables = manager.get_all_tables()
        if len(tables) < 2:
            st.info("Carica almeno due tabelle per definire un Join.")
            
        else:
            col1, col2 = st.columns(2)
            table_left = col1.selectbox("Tabella Sinistra (Left)", list(tables.keys()), key="left_join_table")
            table_right = col2.selectbox("Tabella Destra (Right)", [t for t in tables.keys() if t != table_left], key="right_join_table")
            
            df_L = manager.get_data(table_left)
            df_R = manager.get_data(table_right)
            
            suggestions = suggest_join_keys(df_L, df_R)
            
            st.subheader("🔗 Configurazione Join")
            
            # Logica per suggerimenti predefinita
            default_key_left = suggestions[0][0] if suggestions else df_L.columns[0]
            default_key_right = suggestions[0][1] if suggestions else df_R.columns[0]
            
            if suggestions:
                st.markdown(f"**💡 L'AI suggerisce:** Join tra `{default_key_left}` e `{default_key_right}` (Score: {suggestions[0][2]}%)")

            c1, c2, c3 = st.columns(3)
            key_left = c1.selectbox("Campo Chiave Sinistra", df_L.columns, 
                                    index=df_L.columns.get_loc(default_key_left) if default_key_left in df_L.columns else 0, key="key_left")
            join_type = c2.selectbox("Tipo di Join", ["inner", "left", "right", "outer"], key="join_type")
            key_right = c3.selectbox("Campo Chiave Destra", df_R.columns, 
                                     index=df_R.columns.get_loc(default_key_right) if default_key_right in df_R.columns else 0, key="key_right")

            result_name = st.text_input("Nome del Risultato del Join", "JOIN_Risultato")

            if st.button("Esegui Join e Salva"):
                try:
                    result_df = pd.merge(df_L, df_R, left_on=key_left, right_on=key_right, how=join_type, suffixes=('_L', '_R'))
                    manager.add_dataframe(result_name, result_df, "Joined Data", result_name)
                    st.session_state['last_result_name'] = result_name
                    st.success(f"Join eseguito con successo! Risultato salvato come '{result_name}'.")
                except Exception as e:
                    st.error(f"Errore nel join: {e}")

    # =========================================================================
    # TAB 3: FINAL REPORTING & ANALYSIS
    # =========================================================================
    with tab_reporting:
        st.header("3. Reporting e Analisi Finale")
        
        report_tables = list(manager.get_all_tables().keys())
        if 'last_result_name' in st.session_state and st.session_state['last_result_name'] in report_tables:
            default_idx = report_tables.index(st.session_state['last_result_name'])
        elif report_tables:
            default_idx = 0
        else:
            default_idx = 0
            
        if report_tables:
            df_final_name = st.selectbox("Seleziona il dataset per il Report:", report_tables, index=default_idx, key="final_dataset")
            df_res = manager.get_data(df_final_name).copy()
            
            st.subheader(f"Report: {df_final_name}")
            
            # --- Filtri, Raggruppamento e Somme sulla Tabella Finale ---
            with st.expander("🛠 Opzioni Filtri, Raggruppamento e Calcoli"):
                
                # Filtri Dinamici
                filter_col = st.selectbox("Filtra Report per colonna:", ["Nessuno"] + list(df_res.columns), key="final_filter_col")
                if filter_col != "Nessuno":
                    unique_vals = df_res[filter_col].unique()
                    selected_vals = st.multiselect(f"Valori per {filter_col}", unique_vals, default=unique_vals, key="final_filter_val")
                    df_res = df_res[df_res[filter_col].isin(selected_vals)]
                
                col_group, col_agg = st.columns(2)
                
                with col_group:
                    groupby_col = st.selectbox("Raggruppa Report per:", ["Nessuno"] + list(df_res.columns), key="final_groupby_col")

                with col_agg:
                    numeric_cols = df_res.select_dtypes(include=['number']).columns
                    metric_col = st.selectbox("Colonna Metrica per Somma/Aggregazione", ["Nessuno"] + list(numeric_cols), key="final_metric_col")
            
            # Calcolo aggregazioni (Group By) se richiesto
            if groupby_col != "Nessuno" and metric_col != "Nessuno":
                df_display = df_res.groupby(groupby_col)[metric_col].sum().reset_index()
                df_display = df_display.rename(columns={metric_col: f'SUM_{metric_col}'})
            else:
                df_display = df_res

            
            # --- FUNZIONALITÀ: SELEZIONE E ANALISI IMMEDIATA ---
            st.markdown("---")
            st.markdown("### 🔍 Analisi Veloce (Seleziona le righe nella tabella sottostante)")
            
            # 1. Visualizzazione Tabella Dinamica con selezione righe
            table_with_selection = st.data_editor(
                df_display, 
                use_container_width=True,
                key="final_report_table", 
                column_config={"__index__": st.column_config.CheckboxColumn("Seleziona", default=False)}, 
                hide_index=True
            )
            
            # 2. Ottieni gli indici delle righe selezionate
            selected_rows_indices = table_with_selection[table_with_selection['Seleziona'] == True].index
            
            
            if len(selected_rows_indices) > 0:
                df_analysis = df_display.loc[selected_rows_indices]
                
                st.subheader("Risultati della Selezione")
                
                cols_to_analyze = df_analysis.select_dtypes(include=['number']).columns.tolist()
                can_analyze = False

                if not cols_to_analyze:
                    st.warning("Seleziona una colonna con dati numerici per l'analisi.")
                else:
                    can_analyze = True
                    
                    if metric_col != "Nessuno" and groupby_col == "Nessuno":
                        col_for_analysis = metric_col
                    elif groupby_col != "Nessuno" and metric_col != "Nessuno":
                         col_for_analysis = f'SUM_{metric_col}'
                    elif cols_to_analyze:
                        col_for_analysis = cols_to_analyze[0]
                    else:
                        st.warning("Nessuna colonna numerica valida da analizzare.")
                        can_analyze = False
                    
                
                if can_analyze:
                    # Calcoli
                    total_sum = df_analysis[col_for_analysis].sum()
                    average = df_analysis[col_for_analysis].mean()
                    
                    # Calcolo della variazione percentuale (rispetto al totale del report NON selezionato)
                    total_report_value = df_display[col_for_analysis].sum()
                    if total_report_value != 0:
                        percent_diff = (total_sum / total_report_value) * 100
                    else:
                        percent_diff = 0
                        
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric(f"Totale Selezionato ({col_for_analysis})", f"{total_sum:,.2f} €")
                    c2.metric("Media Selezionata", f"{average:,.2f} €")
                    c3.metric("% sul Totale Report", f"{percent_diff:,.2f} %")
                    
                    st.markdown(f"*(Analisi basata sulla colonna: **{col_for_analysis}**)*")

            else:
                st.info("Seleziona le righe che ti interessano nella tabella per vedere l'analisi immediata.")
            
            # Download
            csv = df_display.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Scarica Report CSV", csv, "final_report.csv", "text/csv")
        
        else:
            st.info("Nessun dato finale disponibile per il report. Esegui prima un Join o carica una tabella.")

if __name__ == "__main__":
    main()
