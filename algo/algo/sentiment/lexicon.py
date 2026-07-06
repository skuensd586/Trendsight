"""Minimal sentiment lexicon for M1; swap for a full lexicon (e.g. Dalian Univ. of Tech.) or a BERT
classifier (M2) once labeled training data is available."""

POSITIVE_WORDS = {
    "支持", "点赞", "赞扬", "满意", "喜欢", "感谢", "欣慰", "振奋", "希望",
    "成功", "进步", "改善", "顺利", "认可", "肯定", "暖心", "好评",
}

NEGATIVE_WORDS = {
    "愤怒", "谴责", "批评", "担忧", "失望", "不满", "抗议", "质疑", "恐慌",
    "悲痛", "谣言", "违规", "事故", "损失", "危机", "崩溃", "差评",
}
