import { Conference } from "@/types/conference";
import { useState } from "react";
import { Tag, Award } from "lucide-react";
import ConferenceYearCell from "./ConferenceYearCell";
import ConferenceDialog from "./ConferenceDialog";
import { conferencesByTitle } from "@/utils/conferenceLoader";

export type SortMode = "deadline" | "name";

export interface TableRow {
  title: string;
  fullName?: string;
  eraRating?: string;
  rankings?: string;
  tags: string[];
  conferences: Map<number, Conference>;
}

interface ConferenceTableProps {
  rows: TableRow[];
  yearColumns: number[];
  sortMode: SortMode;
  onSortChange: (mode: SortMode) => void;
}

const eraBadge = (rating: string) => {
  const cls =
    rating === "a"
      ? "bg-emerald-600 text-white"
      : rating === "b"
      ? "bg-sky-600 text-white"
      : "bg-neutral-400 text-white";
  return (
    <span className={`text-xs font-bold px-2 py-0.5 rounded ${cls} uppercase`}>
      {rating}
    </span>
  );
};

const ConferenceTable = ({ rows, yearColumns, sortMode, onSortChange }: ConferenceTableProps) => {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedConference, setSelectedConference] = useState<Conference | null>(null);

  const handleCellClick = (conference: Conference) => {
    setSelectedConference(conference);
    setDialogOpen(true);
  };

  return (
    <>
      {/* Sort controls */}
      <div className="flex items-center gap-2 mb-3">
        <span className="text-sm text-neutral-400 uppercase tracking-wide font-medium">Sort</span>
        {(["deadline", "name"] as const).map((mode) => (
          <button
            key={mode}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              sortMode === mode
                ? "bg-neutral-800 text-white"
                : "bg-neutral-100 text-neutral-500 hover:bg-neutral-200"
            }`}
            onClick={() => onSortChange(mode)}
          >
            {mode === "deadline" ? "Deadline" : "Name"}
          </button>
        ))}
        <span className="ml-auto text-sm text-neutral-400">{rows.length} conferences</span>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-neutral-200 bg-white overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-neutral-800 text-white">
                <th className="sticky left-0 z-20 bg-neutral-800 text-left px-6 py-3 font-semibold text-sm uppercase tracking-wider min-w-[280px] border-r border-neutral-700">
                  Conference
                </th>
                {yearColumns.map((year, idx) => (
                  <th
                    key={year}
                    className={`text-center px-5 py-3 font-semibold text-sm uppercase tracking-wider min-w-[200px] border-r border-neutral-700 last:border-r-0 ${
                      idx > 0 ? "hidden sm:table-cell" : ""
                    }`}
                  >
                    {year}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rowIdx) => (
                <tr
                  key={row.title}
                  className={`border-b border-neutral-100 transition-all duration-150 hover:shadow-lg hover:z-10 hover:relative hover:bg-blue-50/40 ${
                    rowIdx % 2 === 1 ? "bg-neutral-50/40" : ""
                  }`}
                >
                  {/* Conference info - sticky */}
                  <td className={`sticky left-0 z-10 px-6 py-5 align-top border-r border-neutral-100 min-w-[280px] ${
                    rowIdx % 2 === 1 ? "bg-neutral-50/40" : "bg-white"
                  }`}>
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-lg text-neutral-900">{row.title}</span>
                        {row.eraRating && eraBadge(row.eraRating)}
                      </div>
                      {row.fullName && (
                        <p className="text-sm text-neutral-400 leading-snug">{row.fullName}</p>
                      )}
                      {row.rankings && (
                        <div className="flex items-center gap-1.5 text-xs text-amber-600">
                          <Award className="h-3.5 w-3.5 flex-shrink-0" />
                          <span>{row.rankings}</span>
                        </div>
                      )}
                      {row.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {row.tags.slice(0, 4).map((tag) => (
                            <span key={tag} className="inline-flex items-center text-xs px-2 py-0.5 rounded-full bg-neutral-100 text-neutral-500">
                              <Tag className="h-3 w-3 mr-1" />{tag}
                            </span>
                          ))}
                          {row.tags.length > 4 && (
                            <span className="text-xs text-neutral-400">+{row.tags.length - 4}</span>
                          )}
                        </div>
                      )}
                    </div>
                  </td>

                  {/* Year cells */}
                  {yearColumns.map((year, idx) => (
                    <td
                      key={year}
                      className={`align-top border-r border-neutral-100 last:border-r-0 p-0 ${
                        idx > 0 ? "hidden sm:table-cell" : ""
                      }`}
                    >
                      <ConferenceYearCell
                        conference={row.conferences.get(year)}
                        onClick={handleCellClick}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {selectedConference && (
        <ConferenceDialog
          conference={selectedConference}
          allYears={conferencesByTitle.get(selectedConference.title) || []}
          open={dialogOpen}
          onOpenChange={setDialogOpen}
        />
      )}
    </>
  );
};

export default ConferenceTable;
