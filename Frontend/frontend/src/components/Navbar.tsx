import React, { useState, useEffect } from 'react';
import { NotebookPen, Plus, X, Trash2, Copy, Check, ChevronRight, Pencil, Save } from 'lucide-react';

interface NoteItem {
  id: string;
  title: string;
  content: string;
  timestamp: string;
}

interface NavbarProps {
  currentView: string;
  setView: (view: string) => void;
  backendOnline: boolean;
  activeTicId?: string | null;
  isResultsView?: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({ currentView, setView, activeTicId, isResultsView }) => {
  const [isNotesOpen, setNotesOpen] = useState(false);
  const [savedNotes, setSavedNotes] = useState<NoteItem[]>([]);
  const [activeNote, setActiveNote] = useState<NoteItem | null>(null);
  const [customInput, setCustomInput] = useState('');
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Note editing state
  const [isEditingNote, setIsEditingNote] = useState(false);
  const [editedTitle, setEditedTitle] = useState('');
  const [editedContent, setEditedContent] = useState('');

  // Floating selection popup state
  const [selectedText, setSelectedText] = useState('');
  const [popupPos, setPopupPos] = useState<{ top: number; left: number } | null>(null);

  // Load saved notes from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem('graha_saved_notes');
      if (stored) {
        setSavedNotes(JSON.parse(stored));
      }
    } catch (e) {
      console.error(e);
    }
  }, []);

  // Save notes helper
  const saveNotesList = (notesList: NoteItem[]) => {
    setSavedNotes(notesList);
    try {
      localStorage.setItem('graha_saved_notes', JSON.stringify(notesList));
    } catch (e) {
      console.error(e);
    }
  };

  // Start editing a note
  const startEditing = (note: NoteItem) => {
    setEditedTitle(note.title);
    setEditedContent(note.content);
    setIsEditingNote(true);
  };

  // Save edited note changes
  const handleSaveEditedNote = () => {
    if (!activeNote) return;

    const updatedNote: NoteItem = {
      ...activeNote,
      title: editedTitle.trim() || activeNote.title,
      content: editedContent.trim() || activeNote.content,
      timestamp: activeNote.timestamp.includes('(edited)') ? activeNote.timestamp : `${activeNote.timestamp} (edited)`
    };

    const updatedList = savedNotes.map(n => n.id === activeNote.id ? updatedNote : n);
    saveNotesList(updatedList);
    setActiveNote(updatedNote);
    setIsEditingNote(false);
  };

  // Listen to document selection changes - ONLY allowed in Results View
  useEffect(() => {
    const handleSelectionChange = () => {
      if (!isResultsView) {
        setSelectedText('');
        setPopupPos(null);
        return;
      }

      const selection = window.getSelection();
      const text = selection?.toString().trim();

      if (text && text.length > 0 && selection && selection.rangeCount > 0) {
        try {
          const range = selection.getRangeAt(0);
          const rect = range.getBoundingClientRect();
          if (rect.width > 0 && rect.height > 0) {
            setPopupPos({
              top: rect.top - 46,
              left: rect.left + rect.width / 2
            });
            setSelectedText(text);
            return;
          }
        } catch (e) {
          // Range error fallback
        }
      }
      setSelectedText('');
      setPopupPos(null);
    };

    document.addEventListener('selectionchange', handleSelectionChange);
    return () => {
      document.removeEventListener('selectionchange', handleSelectionChange);
    };
  }, [isResultsView]);

  // Save selected text as a note titled with the TIC ID
  const handleSaveSelectionAsNote = () => {
    if (!selectedText) return;

    const formattedTic = activeTicId
      ? (activeTicId.startsWith('TIC') ? activeTicId : `TIC ${activeTicId}`)
      : 'TIC 737546';
    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const newNote: NoteItem = {
      id: Date.now().toString(),
      title: formattedTic,
      content: selectedText,
      timestamp
    };

    const updated = [newNote, ...savedNotes];
    saveNotesList(updated);

    // Reset selection and popup
    window.getSelection()?.removeAllRanges();
    setSelectedText('');
    setPopupPos(null);
    setNotesOpen(true);
    setActiveNote(newNote);
    setIsEditingNote(false);
  };

  // Add custom manual note
  const handleAddCustomNote = (e: React.FormEvent) => {
    e.preventDefault();
    if (!customInput.trim()) return;

    const words = customInput.trim().split(/\s+/).filter(Boolean);
    const title = words.slice(0, 3).join(' ');
    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const newNote: NoteItem = {
      id: Date.now().toString(),
      title,
      content: customInput.trim(),
      timestamp
    };

    const updated = [newNote, ...savedNotes];
    saveNotesList(updated);
    setCustomInput('');
    setActiveNote(newNote);
    setIsEditingNote(false);
  };

  // Delete note
  const handleDeleteNote = (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    const updated = savedNotes.filter(n => n.id !== id);
    saveNotesList(updated);
    if (activeNote?.id === id) {
      setActiveNote(null);
      setIsEditingNote(false);
    }
  };

  // Copy note content
  const handleCopyNote = (text: string, id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <>
      {/* Floating Popup above selected text - ONLY allowed on Results Screen */}
      {isResultsView && selectedText && popupPos && (
        <div
          style={{
            top: `${Math.max(12, popupPos.top)}px`,
            left: `${popupPos.left}px`,
            transform: 'translateX(-50%)'
          }}
          className="fixed z-[99999] animate-fade-in pointer-events-auto"
        >
          <button
            onMouseDown={(e) => {
              // Prevent default to avoid clearing selection before onClick
              e.preventDefault();
              handleSaveSelectionAsNote();
            }}
            className="bg-white text-black font-mono font-bold text-xs uppercase px-3 py-1.5 shadow-2xl border-2 border-black hover:bg-gray-200 cursor-pointer flex items-center space-x-1.5 rounded-none tracking-wider transition-all duration-150"
          >
            <Plus className="w-3.5 h-3.5 text-black stroke-[3]" />
            <span>SAVE AS NOTE</span>
          </button>
        </div>
      )}

      <header className={`absolute top-0 w-full z-50 transition-all duration-500 ease-in-out ${
        currentView === 'dashboard' ? 'bg-white/95 text-black border-b border-black/10' : 'bg-transparent text-white'
      }`}>
        <div className="flex justify-between items-center px-6 md:px-12 py-6 w-full">
          {/* Logo Brand */}
          <button
            onClick={() => setView('home')}
            className={`font-orbitron font-bold text-2xl tracking-[3px] uppercase hover:opacity-80 transition-opacity cursor-pointer ${
              currentView === 'dashboard' ? 'text-black' : 'text-white'
            }`}
          >
            GRAHA
          </button>

          {/* Navigation Links */}
          <nav className="hidden md:flex gap-8">
            {[
              { id: 'home', label: 'Home' },
              { id: 'dashboard', label: 'Analyzer' },
              { id: 'pipeline', label: 'Workflow' },
              { id: 'about', label: 'Database' }
            ].map((item) => {
              const isActive = currentView === item.id;
              const isDash = currentView === 'dashboard';
              return (
                <button
                  key={item.id}
                  onClick={() => setView(item.id)}
                  className={`font-label-sm text-label-sm uppercase tracking-widest transition-colors ${
                    isActive
                      ? isDash ? 'text-black border-b-2 border-black pb-1 font-bold' : 'text-white border-b-2 border-white pb-1 font-bold'
                      : isDash ? 'text-black/60 hover:text-black pb-1' : 'text-white/60 hover:text-white pb-1'
                  }`}
                >
                  {item.label}
                </button>
              );
            })}
          </nav>

          {/* Right Controls: Notes Drawer Toggle */}
          <div className="flex gap-4 text-on-surface items-center relative">
            <button
              onClick={() => setNotesOpen(!isNotesOpen)}
              className={`p-2.5 rounded-none transition-colors flex items-center justify-center border relative cursor-pointer ${
                currentView === 'dashboard'
                  ? 'hover:bg-black/10 text-black border-black/20'
                  : 'hover:bg-white/10 text-white border-white/20'
              }`}
              title="Saved Notes"
            >
              <NotebookPen className={`w-5 h-5 ${currentView === 'dashboard' ? 'text-black' : 'text-white'}`} />
              {savedNotes.length > 0 && (
                <span className={`absolute -top-1.5 -right-1.5 font-mono font-bold text-[9px] w-4 h-4 flex items-center justify-center rounded-none shadow ${
                  currentView === 'dashboard' ? 'bg-black text-white' : 'bg-white text-black'
                }`}>
                  {savedNotes.length}
                </span>
              )}
            </button>

            {/* Notes Drawer Modal */}
            {isNotesOpen && (
              <div className="absolute top-14 right-0 w-80 sm:w-96 bg-black border border-white/20 rounded-none p-5 shadow-2xl text-white flex flex-col gap-4 z-50 animate-fade-in">
                {/* Header */}
                <div className="flex justify-between items-center border-b border-white/20 pb-3">
                  <div className="flex items-center space-x-2">
                    <NotebookPen className="w-4 h-4 text-white" />
                    <h3 className="font-orbitron font-bold text-xs uppercase tracking-widest text-white">
                      SAVED NOTES ({savedNotes.length})
                    </h3>
                  </div>
                  <button
                    onClick={() => {
                      setNotesOpen(false);
                      setActiveNote(null);
                      setIsEditingNote(false);
                    }}
                    className="p-1 text-white/50 hover:text-white transition-colors cursor-pointer"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                {/* Active Note Detail View */}
                {activeNote ? (
                  <div className="space-y-3 animate-fade-in">
                    <button
                      onClick={() => {
                        setActiveNote(null);
                        setIsEditingNote(false);
                      }}
                      className="text-[10px] font-mono text-white/50 hover:text-white uppercase tracking-wider flex items-center space-x-1 cursor-pointer"
                    >
                      <span>← Back to all notes</span>
                    </button>

                    <div className="border border-white/20 p-4 space-y-3 bg-white/[0.02]">
                      <div className="flex justify-between items-start border-b border-white/10 pb-2">
                        {isEditingNote ? (
                          <input
                            type="text"
                            value={editedTitle}
                            onChange={(e) => setEditedTitle(e.target.value)}
                            className="bg-black border border-white/30 px-2 py-1 font-orbitron font-bold text-xs uppercase text-white outline-none focus:border-white w-full mr-2"
                          />
                        ) : (
                          <div>
                            <h4 className="font-orbitron font-bold text-sm uppercase text-white tracking-wider">
                              {activeNote.title}
                            </h4>
                            <span className="text-[10px] font-mono text-white/40">{activeNote.timestamp}</span>
                          </div>
                        )}
                        <div className="flex space-x-2">
                          {isEditingNote ? (
                            <button
                              onClick={handleSaveEditedNote}
                              className="px-2.5 py-1 bg-white text-black font-mono font-bold text-[10px] uppercase flex items-center space-x-1 hover:bg-gray-200 cursor-pointer rounded-none"
                              title="Save Changes"
                            >
                              <Save className="w-3 h-3 text-black" />
                              <span>SAVE</span>
                            </button>
                          ) : (
                            <button
                              onClick={() => startEditing(activeNote)}
                              className="p-1 text-white/60 hover:text-white transition-colors cursor-pointer"
                              title="Edit Note"
                            >
                              <Pencil className="w-3.5 h-3.5" />
                            </button>
                          )}
                          <button
                            onClick={(e) => handleCopyNote(activeNote.content, activeNote.id, e)}
                            className="p-1 text-white/60 hover:text-white transition-colors cursor-pointer"
                            title="Copy Note"
                          >
                            {copiedId === activeNote.id ? <Check className="w-3.5 h-3.5 text-white" /> : <Copy className="w-3.5 h-3.5" />}
                          </button>
                          <button
                            onClick={(e) => handleDeleteNote(activeNote.id, e)}
                            className="p-1 text-white/60 hover:text-red-400 transition-colors cursor-pointer"
                            title="Delete Note"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>

                      {isEditingNote ? (
                        <textarea
                          value={editedContent}
                          onChange={(e) => setEditedContent(e.target.value)}
                          className="w-full h-40 bg-black border border-white/30 p-2.5 font-mono text-xs text-white outline-none focus:border-white resize-none leading-relaxed"
                          placeholder="Edit note content..."
                        />
                      ) : (
                        <div className="font-mono text-xs text-white/90 leading-relaxed max-h-60 overflow-y-auto whitespace-pre-wrap pr-1">
                          {activeNote.content}
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <>
                    {/* Add Custom Note Input */}
                    <form onSubmit={handleAddCustomNote} className="space-y-2">
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={customInput}
                          onChange={(e) => setCustomInput(e.target.value)}
                          placeholder="Type custom note..."
                          className="flex-1 bg-white/5 border border-white/20 px-3 py-1.5 font-mono text-xs text-white outline-none focus:border-white rounded-none placeholder:text-white/30"
                        />
                        <button
                          type="submit"
                          className="bg-white text-black font-mono font-bold text-xs uppercase px-3 py-1.5 hover:bg-gray-200 cursor-pointer rounded-none"
                        >
                          ADD
                        </button>
                      </div>
                    </form>

                    {/* Notes List */}
                    <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                      {savedNotes.length === 0 ? (
                        <div className="text-center py-6 text-xs font-mono text-white/50 border border-white/10 p-4 leading-relaxed">
                          Analyze a FITS file and select text on the results screen to save it as a note.
                        </div>
                      ) : (
                        savedNotes.map((n) => (
                          <div
                            key={n.id}
                            onClick={() => setActiveNote(n)}
                            className="p-3 border border-white/10 hover:border-white/40 bg-white/[0.02] hover:bg-white/5 transition-all cursor-pointer flex justify-between items-center group"
                          >
                            <div className="space-y-0.5 overflow-hidden pr-2">
                              <div className="font-orbitron font-bold text-xs uppercase text-white truncate tracking-wider">
                                {n.title}
                              </div>
                              <p className="font-mono text-[10px] text-white/50 truncate">
                                {n.content}
                              </p>
                              <div className="text-[9px] font-mono text-white/30">
                                {n.timestamp}
                              </div>
                            </div>
                            <ChevronRight className="w-4 h-4 text-white/30 group-hover:text-white flex-shrink-0 transition-colors" />
                          </div>
                        ))
                      )}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </header>
    </>
  );
};
