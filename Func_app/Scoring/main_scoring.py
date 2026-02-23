import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from scipy.spatial.distance import cdist
from scipy.optimize import linear_sum_assignment
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
    
    # --- Step 1: ดึงข้อมูล T-DTS ---
    raw_tdts_all = [] 
    tdts_list_for_model = [] 
    
    for stock in target_tickers:
        res = analyze_stock_tdts(stock, start_year, end_year, threshold=threshold) 
        if res.get('status') == 'success':
            raw_tdts_all.extend(res['data']['raw_data'])
            tdts_list_for_model.extend(res['data']['clean_data'])
    
    if not tdts_list_for_model:
        return {"status": "error", "message": "No T-DTS data found."}
    
    df_tdts = pd.DataFrame(tdts_list_for_model)

    # --- Step 2: ดึงข้อมูล TEMA ---
    res_tema = analyze_stock_tema(
        tickers=target_tickers, start_year=start_year, end_year=end_year,
        window=window, threshold=threshold
    )
    
    if res_tema.get('status') == 'error': return res_tema

    raw_tema_all = res_tema['data'].get('raw_data', [])
    # prefer clean_data if present, otherwise fall back to raw_data
    tema_records = res_tema['data'].get('clean_data') or res_tema['data'].get('raw_data') or []
    df_tema = pd.DataFrame(tema_records)

    if df_tema.empty:
        return {"status": "error", "message": "No TEMA data found."}

    # --- Step 3: Merge Data ---
    df_tdts['Stock'] = df_tdts['Stock'].str.replace('.BK', '').str.upper()
    df_tema['Stock'] = df_tema['Stock'].str.replace('.BK', '').str.upper()

    df_tdts = df_tdts.rename(columns={'DY_percent': 'DY (%)', 'T-DTS': 'T_DTS'})
    # normalize possible column names from tema
    if 'Ret_Bf_TEMA_Percent' in df_tema.columns:
        df_tema = df_tema.rename(columns={'Ret_Bf_TEMA_Percent': 'Ret_Bf_TEMA (%)', 'Ret_Af_TEMA_Percent': 'Ret_Af_TEMA (%)'})

    # If tema data contains per-XD rows with Ex_Date, merge on Stock+Ex_Date
    if 'Ex_Date' in df_tema.columns:
        df_tdts['Ex_Date'] = pd.to_datetime(df_tdts['Ex_Date'])
        df_tema['Ex_Date'] = pd.to_datetime(df_tema['Ex_Date'])
        df_merged = pd.merge(df_tdts, df_tema[['Stock', 'Ex_Date', 'Ret_Bf_TEMA (%)', 'Ret_Af_TEMA (%)']], on=['Stock', 'Ex_Date'], how='inner')
    else:
        # tema returned aggregated per-stock (no Ex_Date) — merge on Stock only
        df_merged = pd.merge(df_tdts, df_tema[['Stock', 'Ret_Bf_TEMA (%)', 'Ret_Af_TEMA (%)']].drop_duplicates(subset=['Stock']), on=['Stock'], how='left')

    if df_merged.empty:
        return {"status": "error", "message": "Merged data is empty."}

    # --- Step 4: Clustering ---
    df_agg = df_merged.groupby('Stock').aggregate({
        'DY (%)': 'mean', 'T_DTS': 'mean', 
        'Ret_Af_TEMA (%)': 'mean', 'Ret_Bf_TEMA (%)': 'mean'
    }).reset_index()

    df_model = df_agg.dropna().copy()
    

    features = ['T_DTS', 'Ret_Af_TEMA (%)', 'Ret_Bf_TEMA (%)']    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df_model[features])
    
    actual_k = 4 if len(df_model) >= 4 else len(df_model)
    kmeans = KMeans(n_clusters=actual_k, random_state=42, n_init=20)
    df_model['Cluster'] = kmeans.fit_predict(X_scaled)
    
    df_model['Total_Score (%)'] = (df_model['DY (%)'] * (1 - df_model['T_DTS'])) + df_model['Ret_Af_TEMA (%)']

    # ==============================================================================
    # 🎯 Step 5: [THE SOLUTION] Coordinate Matching (จับคู่ตามค่ากลาง)
    # ==============================================================================

    ideal_profiles = {
        'Rebound Star (Buy on Dip)':    np.array([-0.5,  1.0,  1.0]), 
        'Golden Goose (Strong Trend)':  np.array([-1.0,  2.0, -2.0]), 
        'Dividend Trap (Avoid)':        np.array([ 2.5, -3.0, -3.0]), 
        'Sell on Fact (Neutral)':       np.array([ 0.0, -2.0,  1.0])  
    }
    
    profile_names = list(ideal_profiles.keys())
    ideal_vectors = np.array(list(ideal_profiles.values())) # Matrix (4, 3)

    cluster_centroids = []
    cluster_ids = sorted(df_model['Cluster'].unique())
    
    for c_id in cluster_ids:
        mask = df_model['Cluster'] == c_id
        centroid = X_scaled[mask].mean(axis=0)
        cluster_centroids.append(centroid)
    
    cluster_centroids = np.array(cluster_centroids)


    if len(cluster_centroids) > 0:

        distances = cdist(cluster_centroids, ideal_vectors, metric='euclidean')
        row_idx, col_idx = linear_sum_assignment(distances)
        
        cluster_mapping = {}
        for r, c in zip(row_idx, col_idx):
            real_cluster_id = cluster_ids[r]
            assigned_name = profile_names[c]
            cluster_mapping[real_cluster_id] = assigned_name
            
        df_model['Cluster_Name'] = df_model['Cluster'].map(cluster_mapping)
        
    else:
        df_model['Cluster_Name'] = "Unclassified"

    return {
        "status": "success",
        "params": {"start": start_year, "end": end_year, "k": actual_k},
        "count": len(df_model),
        "data": df_model.sort_values(by='Total_Score (%)', ascending=False).to_dict(orient='records'),
        "raw_tdts": raw_tdts_all,
        "raw_tema": raw_tema_all
    }