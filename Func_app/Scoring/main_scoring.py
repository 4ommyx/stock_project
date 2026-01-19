import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from Func_app.config import SET50_TICKERS 
from Func_app.Scoring.tdts_scoring import analyze_stock_tdts
from Func_app.Scoring.tema_scoring import analyze_stock_tema

def process_cluster_and_score(
    tickers: list = None, 
    start_year: int = 2022, 
    end_year: int = 2026,
    window: int = 15,
    threshold: float = 20.0,
    k_clusters: int = 4
):
    
    target_tickers = tickers if tickers else SET50_TICKERS
    
    # --- Data Containers for Caching ---
    raw_tdts_all = [] 
    raw_tema_all = [] 
    tdts_list_for_model = [] 
    
    for stock in target_tickers:
        res = analyze_stock_tdts(stock, start_year, end_year, threshold=20) 
        if res.get('status') == 'success':
            raw_tdts_all.extend(res['data']['raw_data'])
            tdts_list_for_model.extend(res['data']['clean_data'])
    
    if not tdts_list_for_model:
        return {"status": "error", "message": "No T-DTS data found for clustering."}
    
    df_tdts = pd.DataFrame(tdts_list_for_model)

    # --- Step 2: ดึงข้อมูล TEMA ---
    res_tema = analyze_stock_tema(
        tickers=target_tickers, start_year=start_year, end_year=end_year,
        window=window, threshold=threshold
    )
    
    if res_tema.get('status') == 'error': return res_tema

    raw_tema_all = res_tema['data']['raw_data']
    df_tema = pd.DataFrame(res_tema['data']['clean_data'])
    
    if df_tema.empty:
        return {"status": "error", "message": "No TEMA data found for clustering."}

    # --- Step 3: Merge Data ---
    df_tdts['Stock'] = df_tdts['Stock'].str.replace('.BK', '').str.upper()
    df_tema['Stock'] = df_tema['Stock'].str.replace('.BK', '').str.upper()
    df_tdts['Ex_Date'] = pd.to_datetime(df_tdts['Ex_Date'])
    df_tema['Ex_Date'] = pd.to_datetime(df_tema['Ex_Date'])

    df_merged = df_tdts.rename(columns={'DY_percent': 'DY (%)', 'T-DTS': 'T_DTS'})

    tema_cols = ['Stock', 'Ex_Date', 'Ret_Bf_TEMA (%)', 'Ret_Af_TEMA (%)']
    if 'Ret_Bf_TEMA_Percent' in df_tema.columns:
        df_tema = df_tema.rename(columns={'Ret_Bf_TEMA_Percent': 'Ret_Bf_TEMA (%)', 'Ret_Af_TEMA_Percent': 'Ret_Af_TEMA (%)'})

    df_merged = pd.merge(df_merged, df_tema[tema_cols], on=['Stock', 'Ex_Date'], how='inner')

    if df_merged.empty: return {"status": "error", "message": "Merged data is empty."}

    # --- Step 4 & 5: Aggregation & K-Means Clustering ---
    df_agg = df_merged.groupby('Stock').aggregate({
        'DY (%)': 'mean', 'T_DTS': 'mean', 'Ret_Af_TEMA (%)': 'mean', 'Ret_Bf_TEMA (%)': 'mean'
    }).reset_index()

    df_model = df_agg.dropna().copy()
    actual_k = max(1, len(df_model)) if len(df_model) < k_clusters else k_clusters
    
    features = ['T_DTS', 'Ret_Af_TEMA (%)', 'Ret_Bf_TEMA (%)']
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df_model[features])
    
    kmeans = KMeans(n_clusters=actual_k, random_state=42, n_init=10)
    df_model['Cluster'] = kmeans.fit_predict(X_scaled)
    
    # คำนวณ Total Score
    df_model['Total_Score (%)'] = (df_model['DY (%)'] * (1 - df_model['T_DTS'])) + df_model['Ret_Af_TEMA (%)']

    # --- [KEY CHANGE 3] Dynamic Labeling (ตั้งชื่อกลุ่มตามคะแนน ไม่ Hardcode) ---
    cluster_stats = df_model.groupby('Cluster')['Total_Score (%)'].mean().reset_index()
    cluster_stats = cluster_stats.sort_values(by='Total_Score (%)', ascending=False).reset_index(drop=True)
    
    rank_names = [
        'Golden Goose (Strong Trend)',   # Rank 1
        'Rebound Star (Buy on Dip)',     # Rank 2
        'Sell on Fact (Neutral)',        # Rank 3
        'Dividend Trap (Avoid)'          # Rank 4
    ]
    
    cluster_mapping = {}
    for rank, row in cluster_stats.iterrows():
        cluster_id = row['Cluster']
        name = rank_names[rank] if rank < len(rank_names) else f"Group {rank+1}"
        cluster_mapping[cluster_id] = name

    df_model['Cluster_Name'] = df_model['Cluster'].map(cluster_mapping)

    return {
        "status": "success",
        "params": {"start": start_year, "end": end_year, "k": actual_k},
        "count": len(df_model),
        "data": df_model.sort_values(by='Total_Score (%)', ascending=False).to_dict(orient='records'),
        "raw_tdts": raw_tdts_all,
        "raw_tema": raw_tema_all
    }