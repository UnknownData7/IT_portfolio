from sklearn.model_selection import GroupKFold
import pandas as pd
import lightgbm as lgb
import numpy as np
import joblib

df = pd.read_csv('D:/mts/ml_module/data/merged_dataset.csv', low_memory=False)

# удаляем утечку
columns_to_delete = [
    'feat_height_zscore', 'feat_height_quantile', 'B_height',
    'feat_avg_neighbor_height_25m', 'feat_avg_neighbor_height_50m',
    'feat_avg_neighbor_height_100m', 'feat_avg_neighbor_height_200m',
    'B_avg_floor_height', 'gkh_floor_count_max', 'gkh_floor_count_min',
    'Unnamed: 0', 'id', 'B_number', 'match_iou', 'matched_id_b'
]

df = df.drop(columns=columns_to_delete)

# target
y = df['final_height_m']
X = df.drop(columns=['final_height_m'])

# фильтр
mask = y.notna() & (y >= 2.5) & (y < 200)
X = X.loc[mask].copy()
y = y.loc[mask].copy()

groups = X['feat_h3_index'].str[:8]
gkf = GroupKFold(n_splits=7)

models = []
scores = []

for fold, (train_idx, val_idx) in enumerate(gkf.split(X, y, groups)):
    print(f"\nFold {fold + 1}")

    # split ДО feature engineering
    X_train = X.iloc[train_idx].copy()
    X_val = X.iloc[val_idx].copy()
    y_train = y.iloc[train_idx].copy()
    y_val = y.iloc[val_idx].copy()

    for df_part in [X_train, X_val]:
        df_part["h3_8"] = df_part["feat_h3_index"].str[:8]
        df_part["h3_7"] = df_part["feat_h3_index"].str[:7]


        df_part["log_area"] = np.log1p(df_part["area_sq_m"])
        df_part["density_x_area"] = df_part["feat_density_50m"] * df_part["log_area"]

        df_part["coord_sum"] = df_part["feat_x_coord"] + df_part["feat_y_coord"]
        df_part["coord_diff"] = df_part["feat_x_coord"] - df_part["feat_y_coord"]

        df_part["radius"] = np.sqrt(df_part["feat_x_coord"]**2 + df_part["feat_y_coord"]**2)
        df_part["angle"] = np.arctan2(df_part["feat_y_coord"], df_part["feat_x_coord"])

        df_part["density_log"] = np.log1p(df_part["feat_density_50m"])
        df_part["is_zero_density"] = (df_part["feat_density_50m"] == 0).astype(int)

        df_part["area_x_density"] = df_part['area_sq_m'] * df_part["feat_density_50m"]
        df_part["area_x_neighbors"] = df_part["area_sq_m"] * df_part["feat_neighbor_count_50m"]


    h3_stats = X_train.groupby("feat_h3_index")["area_sq_m"].agg(["mean", "std", "count"])
    h3_stats.columns = ["h3_area_mean", "h3_area_std", "h3_count"]

    X_train = X_train.merge(h3_stats, on="feat_h3_index", how="left")
    X_val = X_val.merge(h3_stats, on="feat_h3_index", how="left")

    h3_target = y_train.groupby(X_train["feat_h3_index"]).agg(["mean", "count"])

    global_mean = np.mean(y_train)
    alpha = 20

    smooth = (h3_target['mean'] * h3_target['count'] + global_mean * alpha) / (h3_target['count'] + alpha)

    X_train["h3_height_proxy"] = X_train["feat_h3_index"].map(smooth)
    X_val["h3_height_proxy"] = X_val["feat_h3_index"].map(smooth)

    X_val["h3_height_proxy"] = X_val["h3_height_proxy"].fillna(global_mean)


    y_train_log = np.log1p(y_train)
    y_val_log = np.log1p(y_val)


    X_train_num = X_train.select_dtypes(include=['number']).copy()
    X_val_num = X_val.select_dtypes(include=['number']).copy()

    for col in X_train_num.columns:
        median = X_train_num[col].median()
        X_train_num[col] = X_train_num[col].fillna(median)
        X_val_num[col] = X_val_num[col].fillna(median)


    model = lgb.LGBMRegressor(
        n_estimators=7000,
        learning_rate=0.008,
        num_leaves=512,
        max_depth=-1,
        min_child_samples=3,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_alpha=0.3,
        reg_lambda=0.3,
        random_state=42
    )

    model.fit(
        X_train_num, y_train_log,
        eval_set=[(X_val_num, y_val_log)],
        eval_metric="rmse",
        callbacks=[
            lgb.early_stopping(100),lgb.log_evaluation(200)
        ]
    )


    preds = np.expm1(model.predict(X_val_num))

    rmse = np.sqrt(np.mean((preds - y_val) ** 2))
    print(f"RMSE: {rmse:.4f}")

    models.append(model)
    scores.append(rmse)
artifact = {
    "models": models,
    "features": X_train_num.columns.tolist(),
    "global_mean": global_mean
}
joblib.dump(artifact, 'lgb_pipline.pk1')
print("\nMean RMSE:", np.mean(scores))