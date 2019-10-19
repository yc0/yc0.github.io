---
title: Custom Class with Range-based Loop in C++
date: 2019-10-17 15:06:13
tags:
  - c++
categories:
  - languague
  - c++
---

## Custom Class with Range-based Loop in C++

Sometimes, you have to invent your own class/structure with iteration demands
In modern c++(c++11), it've alread supplied range-based loop. So what's range-based loop?

`for(auto it=begin(arr); it!=end(arr); ++it) {}` is tradional method to iterate the container. range-based loop looks like `for(auto& item : arr)`. It's more comfortable and readable to do iterate. However, how do we implement the same function on your own class/struct ?

## How does Range-base loop work

In the end, the objects returned do not have to actually be iterators. The for(:) loop, unlike most parts of the C++ standard, is [specified to expand to something equivalent to](http://en.cppreference.com/w/cpp/language/range-for):

```c++
for( range_declaration : range_expression )
```

becomes:

```c++
{
  auto && __range = range_expression ;
  for (auto __begin = begin_expr,
            __end = end_expr;
            __begin != __end; ++__begin) {
    range_declaration = *__begin;
    loop_statement
  }
}
```
### how can/must we do

According to previous section, we realize that we have to implement following functions

1. inner class iterator
2. operator!= for inner class iterator 
3. operator++ for inner class iterator
4. dereference for inner class iterator
5. begin()/end()

Here is an example
```c++
template <typename DataType>
 class PodArray {
 public:
   class iterator {
   public:
     iterator(DataType * ptr): ptr(ptr){}
     iterator operator++() { ++ptr; return *this; }
     bool operator!=(const iterator & other) const { return ptr != other.ptr; }
     const DataType& operator*() const { return *ptr; }
   private:
     DataType* ptr;
   };
 private:
   unsigned len;
   DataType *val;
 public:
   iterator begin() const { return iterator(val); }
   iterator end() const { return iterator(val + len); }

   // rest of the container definition not related to the question ...
 };
```