---
date: 2019-10-23 11:25:51
draft: false
slug: Design-a-locker
tags:
- system design
- amazon
- onsite
title: Design a locker
---

## Design a locker

To monitor the process of how to put the package into a right locker. and one locker for one package. your package and locker have different size, you need to make sure the locker size > package.

```
it is just parking lot alike. We can directly manipulate the same concept, or just use the same pattern from Parking Lot
```

### Objects

- Locker
- Location
- Package
- User
- Order
- Shipment

### Work flows

1. Amazon warehouse packages Orders into a Shipment with one or more Packages.
2. Insert created Package(s) into a database and associate them with a Shipment. 
3. Associate Shipment with Order, Associate Order with User.
4. Guarantee that the length, width, and height of each Package cannot exceed the largest Locker's length, width, and height.
5. `(Closest Locker Problem)` Find closest Location of lockers to the Package's destination Location. 
6. `Check the valid volumns`; check that the Location has a volume of Locker spaces greater than or equal to the Package volume (we only need to check volume because step 3 constrains the dimensions). If not, find second closest Locker Location, and so on and so forth.
7. `(Fitting Problem)` Lockers have a set number of sizes (say small, medium, and large). Now, design an algorithm to fit Packages volume into Locker volume, so that minimum amount of Lockers are used. This is easily imagined as a recursive algorithm where you continuously solve for the remaining Packages until the Packages are all fit into Lockers. Each time you fit a package, you return a list of available boxes (remaining spaces in the locker in terms of boxes for that single Locker). If there are no boxes that fit the remaining packages, look for another Locker for the rest of the packages. This method will return the list of Lockers used for the Shipment.
8. Once we know the Packages can be stored at a Locker Location, return the used Locker's Locker IDs and Password to the user (delivery person, recipient, etc).