package dev.mpr.cia;

import java.util.Objects;

/**
 * Represents a JVM method signature at bytecode level.
 *
 * <p>Uses internal JVM class names (with '/') to avoid ambiguity. Callers should
 * normalize names to this format before constructing the identifier.</p>
 */
final class MethodId {

    private final String ownerInternalName;
    private final String name;
    private final String descriptor;

    MethodId(String ownerInternalName, String name, String descriptor) {
        this.ownerInternalName = Objects.requireNonNull(ownerInternalName, "ownerInternalName");
        this.name = Objects.requireNonNull(name, "name");
        this.descriptor = Objects.requireNonNull(descriptor, "descriptor");
    }

    String ownerInternalName() {
        return ownerInternalName;
    }

    String name() {
        return name;
    }

    String descriptor() {
        return descriptor;
    }

    @Override
    public boolean equals(Object obj) {
        if (this == obj) {
            return true;
        }
        if (!(obj instanceof MethodId)) {
            return false;
        }
        MethodId other = (MethodId) obj;
        return ownerInternalName.equals(other.ownerInternalName)
                && name.equals(other.name)
                && descriptor.equals(other.descriptor);
    }

    @Override
    public int hashCode() {
        return Objects.hash(ownerInternalName, name, descriptor);
    }

    @Override
    public String toString() {
        return ownerInternalName + "#" + name + descriptor;
    }
}
