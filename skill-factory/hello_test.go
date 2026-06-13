package main

import "testing"

func TestTwoSum(t *testing.T) {
	cases := []struct {
		name string
		a    int
		b    int
		want int
	}{
		{"正数相加", 2, 3, 5},
		{"负数加正数", -1, 1, 0},
		{"零相加", 0, 5, 5},
		{"两个零", 0, 0, 0},
		{"负数相加", -3, -4, -7},
		{"大数相加", 1000000, 2000000, 3000000},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := twoSum(c.a, c.b)
			if got != c.want {
				t.Errorf("twoSum(%d, %d) = %d, want %d", c.a, c.b, got, c.want)
			}
		})
	}
}