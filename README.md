# 标签自动排版系统 - 横版目标格式

这个版本会生成和目标图片一致的横版 A4 PDF：

- 左侧：主标
- 中间：地址标正面、背面、Logo
- 右侧/下方：有效洗水标
- 自动去除空白洗水标
- 输出 PDF
- 网页显示 PNG 预览

运行：

```bash
cd ~/Desktop/LabelProject_target_format
uvicorn main:app --reload
```

打开：

http://127.0.0.1:8000
