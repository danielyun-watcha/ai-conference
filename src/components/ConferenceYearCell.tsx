import { Conference } from "@/types/conference";
import { getAllDeadlines, getDaysRemaining } from "@/utils/deadlineUtils";
import { getDeadlineInLocalTime } from "@/utils/dateUtils";
import { MapPin, CalendarDays, Clock, Globe, FileText } from "lucide-react";
import { format, isValid } from "date-fns";
import { useAcceptedPapersStatus } from "@/hooks/useAcceptedPapersStatus";

interface ConferenceYearCellProps {
  conference: Conference | undefined;
  onClick?: (conference: Conference) => void;
}

function getAbstractOrPaperDeadline(conference: Conference) {
  const all = getAllDeadlines(conference);
  return (
    all.find(d => d.type === "abstract") ||
    all.find(d => d.type === "paper" || d.type === "submission") ||
    all[0] || null
  );
}

const ConferenceYearCell = ({ conference, onClick }: ConferenceYearCellProps) => {
  const acceptedPapers = useAcceptedPapersStatus(conference?.id);

  if (!conference) {
    return <div className="px-5 py-4 text-sm text-neutral-300 text-center">TBD</div>;
  }

  const acceptedPapersUrl =
    (acceptedPapers?.released && acceptedPapers.url) || conference.accepted_papers_url;
  const showAcceptedPapersBadge = Boolean(acceptedPapers?.released && acceptedPapersUrl);

  const abstractDeadline = getAbstractOrPaperDeadline(conference);
  const location = [conference.city, conference.country].filter(Boolean).join(", ");

  // Calculate days remaining for the displayed deadline (abstract/paper), not next upcoming
  const displayDaysRemaining = abstractDeadline
    ? getDaysRemaining(abstractDeadline, conference.timezone)
    : null;
  const isUpcoming = displayDaysRemaining !== null && displayDaysRemaining > 0;
  const deadlinePast = abstractDeadline
    ? (displayDaysRemaining !== null && displayDaysRemaining <= 0)
    : false;

  const deadlineDateStr = (() => {
    if (!abstractDeadline) return "TBD";
    if (abstractDeadline.date === "TBD") return "TBD";
    const d = getDeadlineInLocalTime(abstractDeadline.date, abstractDeadline.timezone || conference.timezone);
    return d && isValid(d) ? format(d, "MMM d") : "TBD";
  })();

  const badgeClass = !isUpcoming
    ? ""
    : displayDaysRemaining! <= 7
    ? "bg-red-500 text-white"
    : displayDaysRemaining! <= 30
    ? "bg-amber-500 text-white"
    : "bg-emerald-500 text-white";

  return (
    <div
      className="px-5 py-4 cursor-pointer space-y-2"
      onClick={() => onClick?.(conference)}
    >
      {/* Deadline */}
      <div className="flex items-center gap-2">
        <Clock className="h-4 w-4 text-neutral-400 flex-shrink-0" />
        <span className={`text-sm font-medium ${deadlinePast ? "text-neutral-400 line-through" : "text-neutral-800"}`}>
          {deadlineDateStr}
        </span>
        {isUpcoming && (
          <span className={`text-xs font-bold px-2 py-0.5 rounded-full leading-none ${badgeClass}`}>
            {displayDaysRemaining}d
          </span>
        )}
        {deadlinePast && <span className="text-xs text-neutral-400">closed</span>}
      </div>

      {/* Location */}
      <div className="flex items-center gap-2">
        <MapPin className="h-4 w-4 text-neutral-400 flex-shrink-0" />
        <span className="text-sm text-neutral-500">{location || "TBD"}</span>
      </div>

      {/* Dates */}
      <div className="flex items-center gap-2">
        <CalendarDays className="h-4 w-4 text-neutral-400 flex-shrink-0" />
        <span className="text-sm text-neutral-500">{conference.date || "TBD"}</span>
      </div>

      {/* Accepted papers (sits between Dates and Website) */}
      {showAcceptedPapersBadge && (
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-violet-500 flex-shrink-0" />
          <a
            href={acceptedPapersUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium text-violet-600 hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            accepted papers
          </a>
        </div>
      )}

      {/* Website */}
      {conference.link && (
        <div className="flex items-center gap-2">
          <Globe className="h-4 w-4 text-neutral-400 flex-shrink-0" />
          <a
            href={conference.link}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-blue-500 hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            website
          </a>
        </div>
      )}
    </div>
  );
};

export default ConferenceYearCell;
