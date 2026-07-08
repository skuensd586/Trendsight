## 2026-07-08 训练结果 -- text_type=comment

- 训练数据: `data/sentiment_comment.csv`
- 置信度阈值 (confidence_threshold): 0.6
- 选中模型: **LogisticRegression**（held-out 测试集 accuracy 最高）
- 保存路径: `/mnt/d/trendsight/algo/models/sentiment_model_comment_20260708.joblib`

### MultinomialNB

accuracy: 0.7006

```
              precision    recall  f1-score   support

    negative       0.97      0.07      0.13       489
     neutral       0.00      0.00      0.00         0
    positive       0.76      0.99      0.86      1064

    accuracy                           0.70      1553
   macro avg       0.58      0.35      0.33      1553
weighted avg       0.83      0.70      0.63      1553
```

混淆矩阵（标签顺序 ['negative', 'neutral', 'positive']）:

```
[[  34  118  337]
 [   0    0    0]
 [   1    9 1054]]
```

### LogisticRegression

accuracy: 0.8088

```
              precision    recall  f1-score   support

    negative       0.90      0.60      0.72       489
     neutral       0.00      0.00      0.00         0
    positive       0.92      0.90      0.91      1064

    accuracy                           0.81      1553
   macro avg       0.61      0.50      0.54      1553
weighted avg       0.91      0.81      0.85      1553
```

混淆矩阵（标签顺序 ['negative', 'neutral', 'positive']）:

```
[[295 113  81]
 [  0   0   0]
 [ 34  69 961]]
```

---

