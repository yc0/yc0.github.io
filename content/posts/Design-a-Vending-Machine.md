---
date: 2019-10-23 11:13:32
draft: false
slug: Design-a-Vending-Machine
tags:
- system design
- amazon
- onsite
title: Design a Vending Machine
---

## Design a Vending Machine

- Add items to the vending machine in fixed number of slots
- Payment using card or cash
- Select items to dispense

### Think of all objects in reality

Think of all the Real objects :

- Customer
- Product/Item (Product/Item Type (softdrink, cold coffee, cold tea))
- Payment (transaction)
- Cash or Card (Credit/Debit Card)
- Buttom,
- Item Code

### Work Flow

Think about work flow :
1. Customer `select an item` (by entering the code A5)
2. Customer is `presented by item price`
3. Customer `chooses to pay or cancels`
4. Customer can add Card and do payment
5. Payment goes through (Item is despense) else add Card info again
6. Alernatively, Customer `adds bills cal` and `return the change` and `despense the item`

### Design patttern

take those pattern into accout

- Command/Stragegy pattern
- Singleton for Vending machine instance
- Fascade pattern for charing for multiple item

### Reference Design

Actually, I do not like this implementation. But I put here just for reference now.

```c++
struct Product
{
    virtual float getPrice() = 0;
};


struct Water : Product
{
    float getPrice() override {return 1.0;}
};

struct Coke :  Product
{

    float getPrice() override {return 2.0;}
};

struct Payment
{
    virtual float checkout(Product *p) = 0;
};

struct CardPayment : Payment
{
    float checkout(Product *p) override {
        return p->getPrice() * 0.8;
    }
};

struct CashPayment : Payment
{
    float checkout(Product *p) override {
        return p->getPrice() * 1;
    }
};

class VendingMachine
{
private:
    unordered_map<string, Product *> slots;

    int capacity;
    int pay;

public:
    VendingMachine(int cap) : capacity(cap){};

    bool addProduct(string idx, Product *p) {
        if (slots.size() >= capacity) {
            return false;
        }
        slots.insert({idx, p});

        return true;
    }

    Product *order(string idx) {
        auto result = slots[idx];
        if (result) 
            slots.erase(idx);

        return result;
    }

    float checkout(vector<Product *>& prod, Payment *pay) {
        float total = 0;
        for (auto p : prod)
            total += pay->checkout(p);

        return total;
    }
};

class Customer
{
private:
    VendingMachine *vm;
    vector<Product *> cart;

public:
    Customer(VendingMachine *v) : vm(v) {}

    bool select(string idx) {
        Product *p = vm->order(idx);

        if (p) {
            cart.push_back(p);
            return true;
        }
        return false;
    }

    float checkout(Payment *payment) {
        return vm->checkout(cart, payment);
    }
};

int main()
{
    auto w1 = new Water();
    auto w2 = new Water();
    auto c1 = new Coke();
    auto c2 = new Coke();

    auto vm = new VendingMachine(5);
    vm->addProduct("A1", w1);
    vm->addProduct("A2", w2);
    vm->addProduct("A3", c1);
    vm->addProduct("A4", c2);

    Customer *customer = new Customer(vm);
    customer->select("A1");
    customer->select("A2");

    auto card = new CardPayment();
    assert(abs(customer->checkout(card) - 1.6) < 1e-6);

    return 0;
}
```