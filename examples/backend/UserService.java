package backend;

import java.util.*;

public class UserService {

    private Map<String, String> db = new HashMap<>();

    public String find(String id) {
        return db.get(id);
    }

    public void save(String id, String name) {
        db.put(id, name);
    }
}