import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# Import ฟังก์ชันเดิมที่มีอยู่แล้ว เพื่อดึงข้อมูลมาใช้
from Func_app.t_dts_socring import analyze_stock_tdts
from Func_app.tema_socring import analyze_stock_tema

# รายชื่อหุ้น SET50 (Default)
SET50_TICKERS = [
    "ADVANC.BK","AOT.BK","AWC.BK","BANPU.BK","BBL.BK","BDMS.BK","BEM.BK","BGRIM.BK","BH.BK","BJC.BK",
    "BPP.BK","CPALL.BK","CPN.BK","CRC.BK","DELTA.BK","EGCO.BK","ESSO.BK","GULF.BK","HMPRO.BK",
    "IRPC.BK","KBANK.BK","KTB.BK","KTC.BK","LH.BK","MINT.BK","MTC.BK","OR.BK","OSP.BK",
    "PTT.BK","PTTEP.BK","PTTGC.BK","RATCH.BK","SAWAD.BK","SCB.BK","SCC.BK","SCGP.BK","TISCO.BK","TLI.BK",
    "TOP.BK","TTB.BK","TU.BK","VGI.BK","WHA.BK","GLOBAL.BK","BAM.BK","CPAXT.BK","GPSC.BK","BLA.BK"
]

def process_cluster_and_score(
    tickers: list = None, 
    start_year: int = 2022, 
    end_year: int = 2024,
    # [ADDED] รับค่า threshold และ window เข้ามาด้วย
    window: int = 15,
    threshold: float = 20.0,
    k_clusters: int = 4
):
    target_tickers = tickers if tickers else SET50_TICKERS
    
    # --- Step 1: ดึงข้อมูล T-DTS (ต้องวนลูปเพราะฟังก์ชันเดิมรับทีละตัว) ---
    tdts_list = []
    for stock in target_tickers:
        res = analyze_stock_tdts(stock, start_year, end_year, threshold=100) # threshold เยอะๆ เพื่อเอา raw data มาก่อน
        if res.get('status') == 'success':
            # เอา Clean Data หรือ Raw Data ก็ได้ (ในที่นี้เอา clean)
            tdts_list.extend(res['data']['clean_data'])
    
    if not tdts_list:
        return {"status": "error", "message": "No T-DTS data found"}
    
    df_tdts = pd.DataFrame(tdts_list)

# --- Step 2: ดึงข้อมูล TEMA ---
    # [FIX] ส่ง target_tickers, window, threshold ไปให้ครบ
    res_tema = analyze_stock_tema(
        tickers=target_tickers, 
        start_year=start_year, 
        end_year=end_year,
        window=window,
        threshold=threshold
    )
    
    # [FIX] ดักจับ Error ก่อนแปลงเป็น DataFrame
    if isinstance(res_tema, dict) and res_tema.get('status') == 'error':
        return res_tema # ส่ง error กลับไปเลย

    if isinstance(res_tema, dict) and 'data' in res_tema:
         df_tema = pd.DataFrame(res_tema['data']['clean_data'])
    elif isinstance(res_tema, list):
         df_tema = pd.DataFrame(res_tema)
    else:
         # ถ้าไม่เข้าเงื่อนไขข้างบน แสดงว่าโครงสร้างผิดปกติ
         return {"status": "error", "message": "Invalid TEMA response format"}

    if df_tema.empty:
        return {"status": "error", "message": "No TEMA data found"}

    # --- Step 3: Merge Data (ตาม code คุณ) ---
    # จัด Format ชื่อหุ้น
    df_tdts['Stock'] = df_tdts['Stock'].str.replace('.BK', '')
    df_tema['Stock'] = df_tema['Stock'].str.replace('.BK', '') # เผื่อไว้

    # แปลงวันที่
    df_tdts['Ex_Date'] = pd.to_datetime(df_tdts['Ex_Date']) # เช็คชื่อ column ดีๆ ใน tdts_logic อาจจะเป็น Ex_Date หรือ Ex-Date
    df_tema['Ex_Date'] = pd.to_datetime(df_tema['Ex_Date'])

    # เลือก Column TEMA
    # เช็คชื่อ column ให้ตรงกับ output ของ tema_analysis.py
    cols_to_use = ['Stock', 'Ex_Date', 'Ret_Bf_TEMA_Percent', 'Ret_Af_TEMA_Percent'] 
    df_tema_subset = df_tema[cols_to_use]

    # Merge
    df_merged = pd.merge(
        df_tdts, 
        df_tema_subset, 
        on=['Stock', 'Ex_Date'], 
        how='inner'
    )

    if df_merged.empty:
        return {"status": "error", "message": "Merged data is empty"}

    # --- Step 4: Aggregation ---
    # เปลี่ยนชื่อ Column ให้ตรงกับ Logic คุณสำหรับการ Group
    # DY_percent -> DY (%)
    # Ret_Af_TEMA_Percent -> Ret_Af_TEMA (%)
    
    df_agg = df_merged.groupby('Stock').aggregate({
        'DY_percent': 'mean', 
        'T_DTS': 'mean', 
        'Ret_Af_TEMA_Percent': 'mean', 
        'Ret_Bf_TEMA_Percent': 'mean'
    }).reset_index()

    # Rename columns เพื่อให้ง่ายต่อการเรียกใช้ตามสูตรคุณ
    df_agg.columns = ['Stock', 'DY (%)', 'T-DTS', 'Ret_Af_TEMA (%)', 'Ret_Bf_TEMA (%)']

    # --- Step 5: K-Means Clustering ---
    df_model = df_agg.dropna().copy()
    features = ['T-DTS', 'Ret_Af_TEMA (%)', 'Ret_Bf_TEMA (%)']
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df_model[features])
    
    kmeans = KMeans(n_clusters=k_clusters, random_state=42, n_init=10)
    df_model['Cluster'] = kmeans.fit_predict(X_scaled)

    # --- Step 6: Scoring & Naming ---
    df_scoring = df_model.copy()
    
    # สูตร Total Score ของคุณ
    df_scoring['Total_Score (%)'] = (df_scoring['DY (%)'] * (1 - df_scoring['T-DTS'])) + df_scoring['Ret_Af_TEMA (%)']

    # Map ชื่อกลุ่ม
    cluster_names = {
        0: 'Rebound Star (Buy on Dip)',     
        1: 'Golden Goose (Strong Trend)',   
        2: 'Sell on Fact (Neutral)',        
        3: 'Dividend Trap (Avoid)'          
    }
    df_scoring['Cluster_Name'] = df_scoring['Cluster'].map(cluster_names)

    # Sort ตามคะแนน Total Score
    df_scoring = df_scoring.sort_values(by='Total_Score (%)', ascending=False)

    return {
        "status": "success",
        "params": {"start": start_year, "end": end_year, "k": k_clusters},
        "count": len(df_scoring),
        "data": df_scoring.to_dict(orient='records')
    }