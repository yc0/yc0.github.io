---
title: Use exception instead of error code
date: 2019-11-08 17:15:30
tags: ["java","clean code"]
categories: ["java", "OOD"]
---
## Use Exception Instead of Error Code

try/catch 會混淆結構，最好的做法，是將內容從try/catch中抽離出來到一個functions如下：

```java
public void delete(Page page) {
    try {
        deletePageAndAllReference(pages);
    } catch (Exception e) {
        logError(e);
    }
}

private void deletePageAndAllReference(Page page) throws Exception {
    deletePage(page);
    registry.deleteReference(page.name);
    configKeys.deleteKey(page.name.makeKey());  
}
private void logError(Exception e) {    
    logger.log(e.getMessage());
} 
```

In the above, the delete function is all about error processing. It is easy to understand and then ignore. The deletePageAndAllReferences function is all about the processes of fully deleting a page. Error handling can be ignored. This provides a nice separation that makes the code easier to understand and modify.
