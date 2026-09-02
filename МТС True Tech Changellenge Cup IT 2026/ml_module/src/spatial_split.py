from sklearn.model_selection import GroupKFold
import matplotlib.pyplot as plt
import pandas as pd
import lightgbm as lgb
import numpy as np


df = pd.read_csv('D:/mts/ml_module/data/merged_dataset.csv', low_memory=False)



columns_to_delete = ['feat_height_zscore', 'feat_height_quantile', 'B_height', 'feat_avg_neighbor_height_25m',
'B_stairs', 'feat_avg_neighbor_height_50m', 'feat_avg_neighbor_height_100m',
'B_avg_floor_height', 'gkh_floor_count_max', 'feat_avg_neighbor_height_200m',
'gkh_floor_count_min', 'Unnamed: 0', 'id', 'B_number', 'match_iou', 'matched_id_b']

columns = [x for x in df.columns if x not in columns_to_delete]

df_selected = df[columns].copy()

X = df_selected.drop(columns=['final_height_m'])
y = df_selected['final_height_m']

mask = y.notna() & (y >= 2.5) & (y < 200)

groups = df_selected.loc[mask, 'feat_h3_index']
gkf = GroupKFold(n_splits=7)

X_clean = X[mask].copy()
y_clean = y[mask]

# Добавляем доп.фичи
group = X_clean.groupby('feat_h3_index')

X_clean["h3_area_std"] = group["area_sq_m"].transform('std')
X_clean["h3_density_mean"] = group["feat_density_50m"].transform("mean")
X_clean["h3_building_count"] = group["area_sq_m"].transform("count")

# Добавляем фичи
X_clean["h3_parent"] = X_clean["feat_h3_index"].str[:10]
group2 = X_clean.groupby("h3_parent")
X_clean["h3_parent_area_mean"] = group2["area_sq_m"].transform("mean")
X_clean["h3_parent_density"] = group2["feat_density_50m"].transform("mean")

X_clean['x_norm'] = (X_clean["feat_x_coord"] - np.mean(X_clean["feat_x_coord"])) / np.std(X_clean["feat_x_coord"])
X_clean['y_norm'] = (X_clean["feat_y_coord"] - np.mean(X_clean["feat_y_coord"])) / np.std(X_clean["feat_y_coord"])
X_clean["area_x_density"] = X_clean['area_sq_m'] * X_clean["feat_density_50m"]
X_clean["area_x_neighbors"] = X_clean["area_sq_m"] * X_clean["feat_neighbor_count_50m"]
X_clean["density_x_neighbors"] = X_clean["feat_density_50m"] * X_clean["feat_neighbor_count_50m"]
X_clean["coord_sum"] = X_clean["feat_x_coord"] + X_clean["feat_y_coord"]
X_clean["coord_diff"] = X_clean["feat_x_coord"] - X_clean["feat_y_coord"]

X_clean["density_log"] = np.log1p(X_clean["feat_density_50m"])
X_clean["is_zero_density"] = (X_clean["feat_density_50m"] == 0).astype(int)
X_clean["area_bin"] = pd.qcut(X_clean["area_sq_m"], q=10, labels=False)

# H3 как признак
X_clean["h3_int"] = X_clean["feat_h3_index"].apply(lambda x: int(x, 16))
X_clean["h3_area_mean"] = X_clean.groupby("feat_h3_index")["area_sq_m"].transform("mean")

# Радиальные признаки
X_clean["radius"] = np.sqrt(X_clean["feat_x_coord"]**2 + X_clean["feat_y_coord"]**2)
X_clean["angle"] = np.arctan2(X_clean["feat_y_coord"], X_clean["feat_x_coord"])

# Логарифмуем y
y_clean = np.log1p(y_clean)
X_numeric = X_clean.select_dtypes(include=['number'])
for col in X_numeric.columns:
    X_numeric[col] = X_numeric[col].fillna(np.median(X_numeric[col]))

models = []
scores = []
for fold, (train_idx, val_idx) in enumerate(gkf.split(X_numeric, y_clean, groups)):
    print(f"Fold {fold + 1}")

    X_train, X_val = X_numeric.iloc[train_idx], X_numeric.iloc[val_idx]
    y_train, y_val = y_clean.iloc[train_idx], y_clean.iloc[val_idx]

    X_train["h3_height_proxy"] = y_train.groupby(X_train["feat_h3_index"]).transform("mean")
    X_val["h3_height_proxy"] = y_val.groupby(X_val["feat_h3_index"]).transform("mean")

    model = lgb.LGBMRegressor(
        n_estimators=7000,
        learning_rate=0.008,
        max_depth=-1,
        num_leaves=512,
        min_child_samples=3,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_alpha=0.3,
        reg_lambda=0.3,
        random_state=42
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        eval_metric="rmse",
        callbacks=[
            lgb.early_stopping(100),
            lgb.log_evaluation(100)
        ]
    )

    preds = np.expm1(model.predict(X_val))
    rmse = np.sqrt(np.mean((preds - y_val)**2))

    print(f"RMSE: {rmse}")
    lgb.plot_importance(model, max_num_features=20)
    lgb.plot_metric(model, "rmse")
    plt.show()
    models.append(model)
    scores.append(rmse)

print("Mean RMSE:", np.mean(scores))
