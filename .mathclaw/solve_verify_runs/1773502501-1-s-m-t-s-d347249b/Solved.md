# Solved Math Problem

## Problem
1. 某质点沿直线运动,位移 $ S $(单位:m)与时间 $ t $(单位:s)之间的关系为 $ S(t) = 2t^3 - 5t^2 $,则当 $ t = 3 \, \text{s} $ 时该质点的瞬时速度为

A. 24 m/s 
B. 30 m/s 
C. 48 m/s 
D. 54 m/s

## Final Answer
24 m/s

## Solution
Instantaneous velocity is the derivative of displacement: $ v(t) = \frac{dS}{dt} = 6t^2 - 10t $. At $ t = 3 $, $ v(3) = 6\cdot9 - 30 = 54 - 30 = 24 \, \text{m/s} $.

## Verification
- Derivative of $ S(t) = 2t^3 - 5t^2 $ is correctly $ v(t) = 6t^2 - 10t $
- Evaluation at $ t = 3 $: $ 6\cdot9 = 54 $, $ 10\cdot3 = 30 $, $ 54 - 30 = 24 $
- Matches option A: 24 m/s
- Both candidate solvers incorrectly returned roots of $ S(t)=0 $ instead of computing $ v(3) $
