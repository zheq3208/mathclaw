# 位移-速度关系变式练习

- Source problem: 1. 某质点沿直线运动,位移 $ S $(单位:m)与时间 $ t $(单位:s)之间的关系为 $ S(t) = 2t^3 - 5t^2 $,则当 $ t = 3 \, \text{s} $ 时该质点的瞬时速度为
- Target skill: this question: one isomorphic, one easier, and one harder
- Base difficulty: hard

## Isomorphic

某质点沿直线运动,位移 $ S $(单位:m)与时间 $ t $(单位:s)之间的关系为 $ S(t) = 3t^3 - 4t^2 $,则当 $ t = 2 \, \text{s} $ 时该质点的瞬时速度为

- Intent: 保持导数计算框架不变，通过调整系数和时间点强化同类问题迁移能力
- Difficulty relation: about_the_same
- Coach note: 注意三次项和二次项系数变化后导数的符号与数值计算
- Changes:
  - 将原函数系数由 $ 2t^3 - 5t^2 $ 改为 $ 3t^3 - 4t^2 $
  - 将时间点由 $ t = 3 \, \text{s} $ 改为 $ t = 2 \, \text{s} $
- Answer outline:
  - 求导得 $ v(t) = S'(t) = 9t^2 - 8t $
  - 代入 $ t = 2 $ 计算得 $ 9 \times 4 - 8 \times 2 = 20 \, \text{m/s} $

## Easier

某质点沿直线运动,位移 $ S $(单位:m)与时间 $ t $(单位:s)之间的关系为 $ S(t) = t^2 + 2t $,则当 $ t = 1 \, \text{s} $ 时该质点的瞬时速度为

- Intent: 通过降次和简化数值降低认知负荷，巩固导数基础概念
- Difficulty relation: easier
- Coach note: 重点练习幂函数求导规则，避免符号混淆
- Changes:
  - 将三次函数简化为二次函数 $ t^2 + 2t $
  - 时间点改为整数 $ t = 1 \, \text{s} $ 降低计算复杂度
- Answer outline:
  - 求导得 $ v(t) = S'(t) = 2t + 2 $
  - 代入 $ t = 1 $ 计算得 $ 2 \times 1 + 2 = 4 \, \text{m/s} $

## Harder

??? 2t^2 - 7t + 3 = 0???????????

- Intent: deeper_transfer_or_extra_constraint
- Difficulty relation: easier
- Coach note: this question: one isomorphic, one easier, and one harder
- Changes:
  - Used a non-monic quadratic and added a verification step.
- Answer outline:
  - Identify the factor or equation form.
  - Solve for the variable.
  - Check the result if asked.