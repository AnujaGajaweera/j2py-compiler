package reflection;

import java.lang.reflect.*;

public class ReflectionBomb {

    public static void main(String[] args) throws Exception {
        Class<?> cls = Class.forName("java.lang.String");

        Method[] methods = cls.getDeclaredMethods();

        for (Method m : methods) {
            System.out.println(m.getName());
        }
    }
}