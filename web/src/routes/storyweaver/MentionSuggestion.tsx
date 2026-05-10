import { forwardRef, useEffect, useImperativeHandle, useState } from "react";
import { ReactRenderer } from "@tiptap/react";
import type { SuggestionOptions, SuggestionProps } from "@tiptap/suggestion";

import { cn } from "@/lib/cn";

import type { MentionItem } from "./extensions/entity-mention";

interface MentionListProps {
  items: MentionItem[];
  command: (item: MentionItem) => void;
}

interface MentionListHandle {
  onKeyDown: (event: KeyboardEvent) => boolean;
}

const MentionList = forwardRef<MentionListHandle, MentionListProps>(
  ({ items, command }, ref) => {
    const [index, setIndex] = useState(0);

    useEffect(() => {
      // Reset selection when the candidate list changes.
      setIndex(0);
    }, [items]);

    useImperativeHandle(
      ref,
      () => ({
        onKeyDown: (event) => {
          if (items.length === 0) return false;
          if (event.key === "ArrowDown") {
            setIndex((i) => (i + 1) % items.length);
            return true;
          }
          if (event.key === "ArrowUp") {
            setIndex((i) => (i + items.length - 1) % items.length);
            return true;
          }
          if (event.key === "Enter") {
            command(items[index]);
            return true;
          }
          return false;
        },
      }),
      [items, command, index],
    );

    if (items.length === 0) {
      return (
        <div className="rounded-md border border-slate-700 bg-canvas-panel px-3 py-2 text-xs text-slate-500 shadow-lg">
          No matching entities.
        </div>
      );
    }

    return (
      <div className="flex w-72 flex-col rounded-md border border-slate-700 bg-canvas-panel py-1 shadow-lg">
        {items.map((item, i) => (
          <button
            key={item.id}
            type="button"
            onClick={() => command(item)}
            onMouseEnter={() => setIndex(i)}
            className={cn(
              "flex items-baseline justify-between px-3 py-1.5 text-left text-sm transition-colors",
              i === index
                ? "bg-canvas-raised text-slate-100"
                : "text-slate-300 hover:bg-canvas-raised/50",
            )}
          >
            <span>{item.label}</span>
            <span className="text-[10px] uppercase tracking-wider text-slate-500">
              {item.type}
            </span>
          </button>
        ))}
      </div>
    );
  },
);
MentionList.displayName = "MentionList";

/**
 * Tiptap-suggestion render adapter. Wires the popup's lifecycle to a
 * floating `<div>` we position via getBoundingClientRect on the trigger
 * range. Tippy.js would be slicker, but doing it by hand avoids one more
 * dependency for what's effectively three CSS rules.
 */
export function buildSuggestionRenderer(): SuggestionOptions["render"] {
  return () => {
    let component: ReactRenderer<MentionListHandle, MentionListProps> | null = null;
    let popup: HTMLDivElement | null = null;

    const place = (props: SuggestionProps) => {
      if (!popup || !props.clientRect) return;
      const rect = props.clientRect();
      if (!rect) return;
      popup.style.top = `${rect.bottom + window.scrollY + 4}px`;
      popup.style.left = `${rect.left + window.scrollX}px`;
    };

    return {
      onStart: (props) => {
        component = new ReactRenderer(MentionList, {
          props: { items: props.items as MentionItem[], command: props.command },
          editor: props.editor,
        });

        popup = document.createElement("div");
        popup.style.position = "absolute";
        popup.style.zIndex = "100";
        popup.appendChild(component.element);
        document.body.appendChild(popup);
        place(props);
      },
      onUpdate: (props) => {
        component?.updateProps({
          items: props.items as MentionItem[],
          command: props.command,
        });
        place(props);
      },
      onKeyDown: (props) => {
        if (props.event.key === "Escape") {
          popup?.remove();
          component?.destroy();
          popup = null;
          component = null;
          return true;
        }
        return component?.ref?.onKeyDown(props.event) ?? false;
      },
      onExit: () => {
        popup?.remove();
        popup = null;
        component?.destroy();
        component = null;
      },
    };
  };
}
