import joblib
import pandas as pd
import numpy as np

artifact = joblib.load("lgb_pipline.pk1")

models = artifact['models']
features = artifact['features']
global_mean = artifact['global_mean']

df = pd.read_csv('D:/mts/ml_module/data/merged_dataset.csv', low_memory=False)

mask_missing = df['final_height_m'].isna()
X_pred = df.loc[mask_missing].copy()

train_mask = df['final_height_m'].notna() & (df['final_height_m'] >= 2.5) & (df['final_height_m'] < 200)
h3_map = df.loc[train_mask].groupby('feat_h3_index')['final_height_m'].mean()

X_pred["coord_sum"] = X_pred["feat_x_coord"] + X_pred["feat_y_coord"]
X_pred["coord_diff"] = X_pred["feat_x_coord"] - X_pred["feat_y_coord"]

X_pred["radius"] = np.sqrt(X_pred["feat_x_coord"]**2 + X_pred["feat_y_coord"]**2)
X_pred["angle"] = np.arctan2(X_pred["feat_y_coord"], X_pred["feat_x_coord"])

X_pred["density_log"] = np.log1p(X_pred["feat_density_50m"])
X_pred["area_x_density"] = X_pred["area_sq_m"] * X_pred["feat_density_50m"]

X_pred["h3_height_proxy"] = X_pred["feat_h3_index"].map(h3_map)
X_pred["h3_height_proxy"] = X_pred["h3_height_proxy"].fillna(global_mean)

X_pred_num = X_pred.select_dtypes(include=['number']).copy()

for col in features:
    if col not in X_pred_num:
        X_pred_num[col] = 0

X_pred_num = X_pred_num[features]

X_pred_num = X_pred_num.fillna(X_pred_num.median())

preds = np.zeros(len(X_pred_num))

for model in models:
    preds += np.expm1(model.predict(X_pred_num))

preds /= len(models)

df.loc[mask_missing, 'final_height_m'] = preds

df.to_csv('filled_dataset.csv', index=False)