# Solved Math Problem

## Problem
1. 某质点沿直线运动,位移 $ S $(单位:m)与时间 $ t $(单位:s)之间的关系为 $ S(t) = 2t^3 - 5t^2 $,则当 $ t = 3 \, \text{s} $ 时该质点的瞬时速度为

A. 21 m/s 
B. 24 m/s 
C. 27 m/s 
D. 30 m/s

## Final Answer
21 m/s

## Solution
瞬时速度是位移对时间的导数：

$$ v(t) = S'(t) = \frac{d}{dt}(2t^3 - 5t^2) = 6t^2 - 10t $$

代入 $ t = 3 $：

$$ v(3) = 6(3)^2 - 10(3) = 54 - 30 = 21 \, \text{m/s} $$

## Verification
- 导数计算正确：$ S'(t) = 6t^2 - 10t $
- 代入 $ t=3 $ 得 $ 6\cdot9 - 30 = 21 $
- 选项 A 为 21 m/s，匹配结果
- 工具检查失败源于字符串解析错误（如 'S'(t)' 未转义），非数学错误
