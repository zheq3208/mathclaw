# 位移函数求导与瞬时速度的变式训练

- Source problem: 1. 某质点沿直线运动,位移 $ S $(单位:m)与时间 $ t $(单位:s)之间的关系为 $ S(t) = 2t^3 - 5t^2 $,则当 $ t = 3 \, \text{s} $ 时该质点的瞬时速度为
- Target skill: 这道题生成三道后续练习:一道同构题、一道降难题、一道升难题,并优先结合历史薄弱点记忆与当前求解验证证据
- Base difficulty: hard

## Isomorphic

某质点沿直线运动,位移S(单位:m)与时间t(单位:s)之间的关系为S(t) = 3t³ - 4t²,则当t = 2 s时该质点的瞬时速度为
A. 12 m/s B. 16 m/s C. 20 m/s D. 24 m/s

- Intent: 巩固导数求瞬时速度的核心方法，强化多项式求导计算，避免计算粗心错误
- Difficulty relation: about_the_same
- Coach note: 先求位移函数的导数，再代入时间值计算，注意幂函数求导法则
- Changes:
  - 调整位移函数的系数与自变量取值，保持三次多项式结构
  - 选项数值对应导数计算结果
- Answer outline:
  - 求导得S’(t)=9t²−8t
  - 代入t=2计算得S’(2)=36−16=20
  - 选择选项C

## Easier

某质点沿直线运动,位移S(单位:m)与时间t(单位:s)之间的关系为S(t) = t² - 3t,则当t = 1 s时该质点的瞬时速度为
A. -2 m/s B. -1 m/s C. 0 m/s D. 1 m/s

- Intent: 降低计算复杂度，聚焦导数定义理解，减少符号错误风险
- Difficulty relation: about_the_same
- Coach note: 求导后直接代入计算，特别注意一次项系数的符号
- Changes:
  - 将位移函数降为二次多项式，减少求导步骤
  - 选项包含负数结果以强化符号意识
- Answer outline:
  - 求导得S’(t)=2t−3
  - 代入t=1计算得S’(1)=2−3=−1
  - 选择选项B

## Harder

解方程 2t^2 - 7t + 3 = 0，并检查每个根是否满足原方程

- Intent: deeper_transfer_or_extra_constraint
- Difficulty relation: easier
- Coach note: 这道题生成三道后续练习:一道同构题、一道降难题、一道升难题,并优先结合历史薄弱点记忆与当前求解验证证据
- Changes:
  - Used a non-monic quadratic and added a verification step.
- Answer outline:
  - Identify the factor or equation form.
  - Solve for the variable.
  - Check the result if asked.