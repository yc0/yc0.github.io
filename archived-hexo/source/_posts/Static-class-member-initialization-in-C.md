---
title: class static member initialization in C++
tags:
  - c++
  - static
  - initialization
  - lambda
categories:
  - language
  - c++
date: 2019-10-09 11:39:46
---

## class static member initialization in C++
How we initialize the class static member and make a simliar concept of Java static scope is shown in below `如何初始化Static class member和達成類似Java Static Scope的功能，將是本文紀錄的項目`。

#### Class Static Member 
At first, class static member must be initialized, for example.
```
class CFoo {
public:
    CFoo() {}
    int GetData() { return s_data; }
private:
    static int s_data;
};
 
void main() {
    CFoo foo;
    cout << foo.GetData() << endl;
}
```
it will incur following errors:

`error LNK2001: unresolved external symbol “private: static int CFoo::s_data” (?s_data@CFoo@@0HA)`

Besides, you CANNOT DO THIS in your class for initialization static member with *non-const*
```
class CFoo {
public:
    CFoo() : m_b(15) {}
private:
    static int m_a = 15;   // not allow
    static int m_b;
};
```
Complier would tell you:

`
error C2864: ‘CFoo::m_a’ : a static data member with an in-class initializer must have non-volatile const integral type
error C2438: ‘m_b’ : cannot initialize static class data via constructor
`

When mentioning non-const, I also imply that initializing static const variables initialized in class is allowed.

In other word, if const static member is integral type in a class, it can be initialized in place.
```
class CFoo {
private:
    static const int m_a = 15;
};
```
Perfectly, for now, we can initial our static members if they are integral and const,non-volatile.
But,what if they are not integral type, how can we initialize them ?

#### Non-const and Non-integral Type Static Member Inialization

If the member is non-itegral and non-const, it is not allowed either.
```
class CFoo {
private:
    static const string m_str = "Bar";
};
```
Compiler would warn you:

`
error C2864: ‘CFoo::m_str’ : a static data member with an in-class initializer must have non-volatile const integral type
`

As a result, you have to declare static members in a class, and define them outside the class for non-const and non-integral type, for instance :
```
class CFoo {
private:
    static int m_data;
    static const string m_str;
};
 
int CFoo::m_data = 15;
const string CFoo::m_str = "Bar";
```
#### Initialize Static Member Using Lambda

C++11 also give us great tool-lambda. We can do this like following to fullfill the static block concept like JAVA
```
class A {
private:
    static vector<int> ve;
};
vector<int> A::ve = []() -> vector<int> {
    vector<int> ref(30);
    return ref;
}();
```

