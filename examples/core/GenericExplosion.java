package core;

import java.util.*;

public class GenericExplosion {

    public static Map<String, List<Map<Integer, List<String>>>> build() {
        Map<String, List<Map<Integer, List<String>>>> data = new HashMap<>();

        List<Map<Integer, List<String>>> list = new ArrayList<>();
        Map<Integer, List<String>> inner = new HashMap<>();

        inner.put(1, Arrays.asList("a", "b", "c"));
        list.add(inner);
        data.put("key", list);

        return data;
    }
}