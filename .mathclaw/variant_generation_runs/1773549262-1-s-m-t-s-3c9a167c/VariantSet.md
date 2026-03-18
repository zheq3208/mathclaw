# 位移与瞬时速度关系变式训练

- Source problem: 1. 某质点沿直线运动,位移 $ S $(单位:m)与时间 $ t $(单位:s)之间的关系为 $ S(t) = 2t^2 - 5t^2 $,则当 $ t = 3 \, \text{s} $ 时该质点的瞬时速度为
- Target skill: this question: one isomorphic, one easier, and one harder
- Base difficulty: hard

## Isomorphic

1. 某质点沿直线运动,位移 $ S $(单位:m)与时间 $ t $(单位:s)之间的关系为 $ S(t) = 3t^3 - 4t^2 $,则当 $ t = 2 \, \text{s} $ 时该质点的瞬时速度为

- Intent: 保持相同解题框架（三次函数求导），但调整系数和时间点以避免机械记忆，强化导数运算流程
- Difficulty relation: about_the_same
- Coach note: 注意 $ -4t^2 $ 的导数符号易错，计算时需逐项验证
- Changes:
  - 将原函数系数由 $ 2t^3 - 5t^2 $ 改为 $ 3t^3 - 4t^2 $
  - 将时间点由 $ t = 3 \, \text{s} $ 改为 $ t = 2 \, \text{s} $
- Answer outline:
  - 求导得 $ S'(t) = 9t^2 - 8t $
  - 代入 $ t = 2 $ 计算 $ 9 \times 4 - 8 \times 2 = 20 $

## Easier

1. 某质点沿直线运动,位移 $ S $(单位:m)与时间 $ t $(单位:s)之间的关系为 $ S(t) = t^2 - 3t $,则当 $ t = 1 \, \text{s} $ 时该质点的瞬时速度为

- Intent: 通过简化函数次数和数值，聚焦导数基础概念，减少计算干扰
- Difficulty relation: about_the_same
- Coach note: 二次函数求导更直观，重点检查 $ -3t $ 的导数符号
- Changes:
  - 将三次函数简化为二次函数 $ t^2 - 3t $
  - 降低时间点计算复杂度
- Answer outline:
  - 求导得 $ S'(t) = 2t - 3 $
  - 代入 $ t = 1 $ 计算 $ 2 \times 1 - 3 = -1 $

## Harder

1. 某质点沿直线运动,位移 $ S $(单位:m)与时间 $ t $(单位:s)之间的关系为 $ S(t) = -\frac{1}{2}t^3 + 4t^2 - 5t $,则当 $ t = 3 \, \text{s} $ 时该质点的瞬时速度为

- Intent: 通过分数系数和多重符号组合，暴露符号错误和计算疏漏风险
- Difficulty relation: about_the_same
- Coach note: 特别注意分数系数的导数运算和连续负号叠加
- Changes:
  - 引入分数系数 $ -\frac{1}{2}t^3 $
  - 增加常数项 $ -5t $
  - 强化负号运算复杂度
- Answer outline:
  - 求导得 $ S'(t) = -\frac{3}{2}t^2 + 8t - 5 $
  - 代入 $ t = 3 $ 计算 $ -\frac{3}{2} \times 9 + 8 \times 3 - 5 = -13.5 + 24 - 5 = 5.5 $