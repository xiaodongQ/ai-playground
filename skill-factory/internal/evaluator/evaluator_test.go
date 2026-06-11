package evaluator

import "testing"

func TestParseEval(t *testing.T) {
	cases := []struct {
		name      string
		in        string
		wantScore int
		wantCmt   string
	}{
		{
			name:      "标准 X/10",
			in:        "评分: 8/10\n评语: 完美完成",
			wantScore: 8,
			wantCmt:   "完美完成",
		},
		{
			name:      "无 /10 后缀",
			in:        "评分: 10\n评语: 全部完成",
			wantScore: 10,
			wantCmt:   "全部完成",
		},
		{
			name:      "中文冒号",
			in:        "评分：7\n评语：还行",
			wantScore: 7,
			wantCmt:   "还行",
		},
		{
			name:      "0 分 + 评语（实际 claude 自相矛盾场景）",
			in:        "评分: 0\n评语: 完美完成",
			wantScore: 0,
			wantCmt:   "完美完成",
		},
		{
			name:      "无评语",
			in:        "评分: 5",
			wantScore: 5,
			wantCmt:   "评分: 5", // 全文 fallback
		},
		{
			name:      "完全乱码",
			in:        "I don't know how to format this",
			wantScore: 0, // 解析失败 fallback
			wantCmt:   "I don't know how to format this",
		},
		{
			name:      "多行输出（claude 常见）",
			in:        "我先分析一下...\n评分: 9\n评语: 一次性通过",
			wantScore: 9,
			wantCmt:   "一次性通过",
		},
	}
	for _, c := range cases {
		got := parseEval(c.in)
		if got.Score != c.wantScore {
			t.Errorf("%s: score = %d, want %d", c.name, got.Score, c.wantScore)
		}
		if got.Comments != c.wantCmt {
			t.Errorf("%s: comments = %q, want %q", c.name, got.Comments, c.wantCmt)
		}
	}
}
