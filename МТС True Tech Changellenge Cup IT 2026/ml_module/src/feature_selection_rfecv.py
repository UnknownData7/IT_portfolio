from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_selection import RFECV
from sklearn.model_selection import KFold
import pandas as pd

rfr = RandomForestRegressor(criterion='absolute_error', max_depth=5, bootstrap=True, n_jobs=3, random_state=42)
print('Загружаем RFECV')
rfecv = RFECV(
    estimator=rfr,
    step=1,
    cv=KFold(5),
    scoring='r2',
    n_jobs=-1,
    min_features_to_select=1
)

print("Загружаем датасет")
df = pd.read_csv('D:/mts/ml_module/data/merged_dataset.csv')
X = df.drop(columns=['final_height_m'])
y = df['final_height_m']

mask = y.notna() & (y > 2.5) & (y < 200)
X_clean = X[mask].fillna(0)
y_clean = y[mask]

X_numeric = X_clean.select_dtypes(include=['number'])

X_numeric = X_numeric[:10000]
y_clean = y_clean[:10000]

print("Обучаем")
rfecv.fit(X_numeric, y_clean)

ranking_df = pd.DataFrame({
    "Feature": X_numeric.columns,
    "Ranking": rfecv.ranking_
})

print(ranking_df.sort_values(by='Ranking'))

"""
feat_height_zscore, feat_height_quantile, B_height, feat_avg_neighbor_height_25m,
B_stairs, feat_avg_neighbor_height_50m, feat_avg_neighbor_height_100m,
B_avg_floor_height, feat_avg_neighbor_height_200m, gkh_floor_count_max,
gkh_floor_count_min, Unnamed: 0, id - колонки для удаления (причины в файле "результаты отбора RFECV.txt")
"""