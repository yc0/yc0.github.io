---
title: C++ Print Pretty
tags:
  - c++
categories:
  - language
  - c++
date: 2019-10-05 08:57:42
---

## C++ Print Pretty
So for anyone unfamiliar, C++ has a variety of things called **manipulators** that will change the format of the output printed with "cout". These things are not printed themselves, they just affect the part you are actually printing. A list of these manipulators can be found on [the reference](http://www.cplusplus.com/reference/library/manipulators/)

Here is an example

**input**
```
100.345 2006.008 2331.41592653498
```
**output**
```
0x64             
_______+2006.01  
2.331415927E+03
```
How can we do that ? Yes, use **manipulators**

### Source Code
```c++
double A = 100.345; // 16 bytes for long long
double B = 2006.008;
double C = 2331.41592653498;

// LINE 1 
cout << hex << left << showbase << nouppercase; // formatting
cout << (long long) A << endl; // actual printed part

// LINE 2
cout << dec << right << setw(15) << setfill('_') << showpos << fixed << setprecision(2); // formatting
cout << B << endl; // actual printed part

// LINE 3
cout << scientific << uppercase << noshowpos << setprecision(9); // formatting
cout << C << endl; // actual printed part
```
The explanation shows as follows
### Print Line 1

+ **hex**: 
output the number in hexadecimal format
+ **left**: align the number to the left
+ **showbase**: make sure the hexadecimal number has a '0x' at the beginning
+ **nouppercase**: converts all alphabetic hexadecimal values to lowercase.

### Print Line 2
+ **dec**: switches numbers from hexadecimal back to decimal.
+ **right**: aligns values to the right instead of the left
+ **setw(15)**: sets a fixed width of 15, as the effect from the initial code only impacts the first printed line.
+ **setfill(*)**: by default, when you have a fixed width, if your printed value doesn't fill up the entire length (for example, if you have a width of 15 and only print 7 characters), the extra characters used **to pad are whitespaces**. This function lets you change the padding to whatever character you want.
+ **showpos**: Makes sure there is a **plus/negative sign** before any positive numbers
+ **fixed**: ensures that number is printed out entirely and that scientific notation isn't used for larger numbers
+ **setprecision(*)**: sets the number of decimal places to 2.

### Print Line 3
+ **scientific**: prints output in scientific notation format
+ **uppercase**: undoes previous nouppercase manipulator and ensures that the 'E' in the scientific notation is capitalised
+ **noshowpos**: undoes previous showpos manipulator and gets rid of the plus/negative sign at the start of positive values
+ **setprecision**: changes the number of digits after the decimal place from 2 to 9.


